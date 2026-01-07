# MCP Multi-Worker Coordination

## Purpose
Coordinate MCP subprocess ownership across multiple Puma workers using PostgreSQL row-level locks. Ensures only one worker manages each Docker container.

## The Problem

In multi-worker environments (Puma with multiple workers):
- Each worker is a separate process
- Without coordination, multiple workers could start the same MCP container
- Need to ensure exactly one worker "owns" each subprocess

## Solution: Database-Backed PID Locks

Use PostgreSQL row-level locking to coordinate process ownership:

```ruby
# app/models/mcp_server_instance.rb
class MCPServerInstance < ApplicationRecord
  belongs_to :agent, class_name: "Agent"
  belongs_to :tool, class_name: "Tool"

  validates :mode, presence: true, inclusion: { in: %w[remote subprocess] }
  validates :status, presence: true, inclusion: { in: %w[stopped starting running failed] }
  validates :agent_id, uniqueness: { scope: :tool_id }

  validate :validate_mode_specific_config

  # Scopes
  scope :running, -> { where(status: "running") }
  scope :subprocess_mode, -> { where(mode: "subprocess") }
  scope :remote_mode, -> { where(mode: "remote") }

  # Lock coordination constants
  COORDINATION_LOCK_TTL = 300  # 5 minutes
  STALE_THRESHOLD = 1.hour     # For UI display

  # Acquire exclusive lock for supervising this instance
  def self.acquire_supervisor_lock(agent_id, tool_id)
    existing = where(agent_id: agent_id, tool_id: tool_id).first

    if existing
      return existing if existing.owned_by_current_process?

      if existing.can_be_claimed?
        begin
          existing.with_lock do
            return existing if existing.can_be_claimed?
            nil  # Someone else claimed it
          end
        rescue ActiveRecord::LockWaitTimeout
          nil
        end
      else
        nil  # Already owned by someone else
      end
    else
      # Create new instance with FOR UPDATE NOWAIT
      begin
        default_config = {
          "command" => "docker",
          "args" => ["run", "--rm", "-i", "default-mcp-server"],
          "env" => {},
          "startup_timeout" => 30
        }

        where(agent_id: agent_id, tool_id: tool_id)
          .lock("FOR UPDATE NOWAIT")
          .first_or_create!(
            agent_id: agent_id,
            tool_id: tool_id,
            mode: "subprocess",
            status: "stopped",
            config: default_config
          )
      rescue ActiveRecord::RecordNotUnique, PG::LockNotAvailable
        nil  # Another worker created it first
      end
    end
  end

  # Claim ownership of this instance
  def acquire_lock!
    update!(
      supervisor_pid: Process.pid,
      started_at: Time.current,
      status: "starting"
    )
  end

  # Release ownership
  def release_lock!
    update!(
      supervisor_pid: nil,
      stopped_at: Time.current,
      status: "stopped"
    )
  end

  # Ownership checks
  def owned_by_current_process?
    supervisor_pid == Process.pid && status.in?(%w[starting running])
  end

  def owned_by_other_process?
    supervisor_pid.present? &&
      supervisor_pid != Process.pid &&
      status.in?(%w[starting running])
  end

  def stale?
    return true if supervisor_pid.blank?
    return false unless started_at
    (Time.current - started_at) > COORDINATION_LOCK_TTL.seconds
  end

  def can_be_claimed?
    status.in?(%w[stopped failed]) || stale? || !process_alive?
  end

  def process_alive?
    return false unless supervisor_pid
    Process.kill(0, supervisor_pid)
    true
  rescue Errno::ESRCH, Errno::EPERM
    false
  end

  # Status management
  def mark_running!
    update!(status: "running", started_at: Time.current)
  end

  def mark_failed!(error_message = nil)
    update!(
      status: "failed",
      stopped_at: Time.current,
      config: config.merge("last_error" => error_message)
    )
  end

  # UI helpers
  def stale_for_ui?
    status == "running" &&
      (last_activity_at.nil? || last_activity_at < STALE_THRESHOLD.ago)
  end

  private

  def validate_mode_specific_config
    case mode
    when "remote"
      errors.add(:config, "endpoint required for remote mode") if config["endpoint"].blank?
    when "subprocess"
      errors.add(:config, "only docker command supported") unless config["command"] == "docker"
      errors.add(:config, "args required for subprocess mode") if config["args"].blank?
    end
  end
end
```

## Database Migration

```ruby
# db/migrate/create_mcp_server_instances.rb
class CreateMCPServerInstances < ActiveRecord::Migration[7.0]
  def change
    create_table :mcp_server_instances, id: :uuid do |t|
      t.references :agent, type: :uuid, foreign_key: true, null: false
      t.references :tool, type: :uuid, foreign_key: true, null: false

      t.string :mode, null: false, default: "subprocess"
      t.string :status, null: false, default: "stopped"
      t.jsonb :config, null: false, default: {}

      # Process coordination
      t.integer :supervisor_pid
      t.datetime :started_at
      t.datetime :stopped_at
      t.datetime :last_activity_at

      t.timestamps

      t.index [:agent_id, :tool_id], unique: true
      t.index :status
      t.index :supervisor_pid
    end
  end
end
```

## Integration Pattern

Use in agent or service that manages MCP servers:

```ruby
class Agent < ApplicationRecord
  def start_mcp_servers!
    mcp_tools.each do |tool|
      start_mcp_server_for_tool(tool)
    end
  end

  def start_mcp_server_for_tool(tool)
    # Try to acquire lock for this tool
    instance = MCPServerInstance.acquire_supervisor_lock(id, tool.id)

    unless instance
      Rails.logger.info "MCP server for #{tool.name} owned by another worker"
      return nil
    end

    # We own it - start the supervisor
    begin
      instance.acquire_lock!

      supervisor = build_supervisor_for_tool(tool, instance.config)
      supervisor.start

      instance.mark_running!

      # Store supervisor reference
      store_supervisor(tool.id, supervisor)

      supervisor
    rescue => e
      instance.mark_failed!(e.message)
      raise
    end
  end

  def stop_mcp_servers!
    mcp_tools.each do |tool|
      stop_mcp_server_for_tool(tool)
    end
  end

  def stop_mcp_server_for_tool(tool)
    instance = mcp_server_instances.find_by(tool: tool)
    return unless instance&.owned_by_current_process?

    supervisor = get_supervisor(tool.id)
    supervisor&.stop

    instance.release_lock!
    clear_supervisor(tool.id)
  end

  private

  # In-memory supervisor storage (per-process)
  def store_supervisor(tool_id, supervisor)
    @supervisors ||= {}
    @supervisors[tool_id] = supervisor
  end

  def get_supervisor(tool_id)
    @supervisors&.dig(tool_id)
  end

  def clear_supervisor(tool_id)
    @supervisors&.delete(tool_id)
  end
end
```

## Stale Lock Recovery

Handle workers that died without releasing locks:

```ruby
# lib/tasks/mcp.rake
namespace :mcp do
  desc "Clean up stale MCP server locks"
  task cleanup_stale_locks: :environment do
    stale_instances = MCPServerInstance
      .where(status: %w[starting running])
      .where("started_at < ?", MCPServerInstance::COORDINATION_LOCK_TTL.seconds.ago)

    stale_instances.find_each do |instance|
      next if instance.process_alive?

      Rails.logger.info "Releasing stale lock for #{instance.tool.name}"
      instance.release_lock!
    end
  end
end
```

Run periodically:

```ruby
# config/schedule.rb
every 5.minutes do
  rake "mcp:cleanup_stale_locks"
end
```

## Worker Shutdown Hook

Clean up on worker shutdown:

```ruby
# config/puma.rb
on_worker_shutdown do
  Rails.logger.info "Puma worker shutting down, releasing MCP locks"

  MCPServerInstance.where(supervisor_pid: Process.pid).find_each do |instance|
    Rails.logger.info "Releasing lock for #{instance.tool.name}"
    instance.release_lock!
  end
end
```

Or in an initializer:

```ruby
# config/initializers/mcp_shutdown_hook.rb
at_exit do
  MCPServerInstance.where(supervisor_pid: Process.pid).update_all(
    supervisor_pid: nil,
    status: "stopped",
    stopped_at: Time.current
  )
end
```

## Monitoring Dashboard

Check MCP server status across workers:

```ruby
# app/controllers/mcp_containers_controller.rb
class MCPContainersController < ApplicationController
  def index
    @instances = MCPServerInstance.includes(:agent, :tool).order(:created_at)
  end

  def show
    @instance = MCPServerInstance.find(params[:id])
  end

  def restart
    instance = MCPServerInstance.find(params[:id])

    # Force release if owned by dead process
    if instance.can_be_claimed?
      instance.release_lock!
      flash[:notice] = "Lock released, container can be restarted"
    else
      flash[:alert] = "Cannot restart: owned by PID #{instance.supervisor_pid}"
    end

    redirect_to mcp_containers_path
  end

  def cleanup_stale
    count = 0
    MCPServerInstance.where(status: %w[starting running]).find_each do |instance|
      if instance.can_be_claimed?
        instance.release_lock!
        count += 1
      end
    end

    flash[:notice] = "Released #{count} stale locks"
    redirect_to mcp_containers_path
  end
end
```

## Testing

```ruby
RSpec.describe MCPServerInstance do
  describe ".acquire_supervisor_lock" do
    it "creates new instance if none exists" do
      agent = create(:agent)
      tool = create(:tool)

      instance = described_class.acquire_supervisor_lock(agent.id, tool.id)

      expect(instance).to be_present
      expect(instance.status).to eq("stopped")
    end

    it "returns existing instance if owned by current process" do
      existing = create(:mcp_server_instance,
        supervisor_pid: Process.pid,
        status: "running")

      instance = described_class.acquire_supervisor_lock(
        existing.agent_id,
        existing.tool_id
      )

      expect(instance.id).to eq(existing.id)
    end

    it "returns nil if owned by another active process" do
      other_pid = Process.pid + 1000
      existing = create(:mcp_server_instance,
        supervisor_pid: other_pid,
        status: "running",
        started_at: 1.minute.ago)

      # Mock process_alive? to return true
      allow_any_instance_of(described_class)
        .to receive(:process_alive?).and_return(true)

      instance = described_class.acquire_supervisor_lock(
        existing.agent_id,
        existing.tool_id
      )

      expect(instance).to be_nil
    end

    it "claims stale instance from dead process" do
      existing = create(:mcp_server_instance,
        supervisor_pid: 99999,  # Non-existent PID
        status: "running",
        started_at: 10.minutes.ago)

      instance = described_class.acquire_supervisor_lock(
        existing.agent_id,
        existing.tool_id
      )

      expect(instance.id).to eq(existing.id)
    end
  end

  describe "#can_be_claimed?" do
    it "returns true for stopped status" do
      instance = build(:mcp_server_instance, status: "stopped")
      expect(instance.can_be_claimed?).to be true
    end

    it "returns true for failed status" do
      instance = build(:mcp_server_instance, status: "failed")
      expect(instance.can_be_claimed?).to be true
    end

    it "returns true if stale" do
      instance = build(:mcp_server_instance,
        status: "running",
        started_at: 10.minutes.ago)

      expect(instance.can_be_claimed?).to be true
    end

    it "returns false if recently started and running" do
      instance = build(:mcp_server_instance,
        status: "running",
        supervisor_pid: Process.pid + 1,
        started_at: 1.minute.ago)

      allow(instance).to receive(:process_alive?).and_return(true)

      expect(instance.can_be_claimed?).to be false
    end
  end
end
```

## Best Practices

1. **Short lock TTL**: Use 5-minute TTL to recover from crashes quickly
2. **Check process_alive?**: Don't just trust PID, verify process exists
3. **Graceful shutdown**: Always release locks on worker shutdown
4. **Periodic cleanup**: Run cleanup task every few minutes
5. **Monitor stale locks**: Alert if locks are stale for too long
6. **Use NOWAIT**: Fail fast rather than blocking on locks

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Lock contention | Many workers starting | Use NOWAIT, handle nil result |
| Orphaned locks | Worker crashed | Run cleanup task, check process_alive? |
| PID reuse | OS reused PID | Combine PID check with timestamp |
| Lock not released | Exception during stop | Use ensure blocks, at_exit hooks |
