# File Attachments

Handle file uploads and attachments in ChatKit.

## Attachment Model

Track uploaded files per account/agent/user:

```ruby
# app/models/chatkit_attachment.rb
class ChatkitAttachment < ApplicationRecord
  belongs_to :blob, class_name: "ActiveStorage::Blob"
  belongs_to :account
  belongs_to :agent, optional: true
  belongs_to :user, optional: true

  validates :blob, presence: true
  validates :account, presence: true
end
```

### Migration

```ruby
class CreateChatkitAttachments < ActiveRecord::Migration[7.1]
  def change
    create_table :chatkit_attachments, id: :uuid do |t|
      t.references :blob, null: false, foreign_key: { to_table: :active_storage_blobs }, type: :uuid
      t.references :account, null: false, foreign_key: true, type: :uuid
      t.references :agent, foreign_key: true, type: :uuid
      t.references :user, foreign_key: true, type: :uuid
      t.timestamps
    end
  end
end
```

## Upload Endpoint

```ruby
def upload
  unless requested_agent
    return render(json: { error: I18n.t("chatkit.errors.agent_required") }, status: :unprocessable_content)
  end

  file = params[:file]
  unless file.respond_to?(:size)
    render json: { error: I18n.t("chatkit.errors.file_required") }, status: :unprocessable_content
    return
  end

  error = validate_attachment(file.original_filename, file.size, file.content_type)
  return render(json: { error: error }, status: :unprocessable_content) if error

  blob = ActiveStorage::Blob.create_and_upload!(
    io: file,
    filename: file.original_filename,
    content_type: file.content_type
  )

  ChatkitAttachment.create!(
    blob: blob,
    account: Current.account,
    agent: requested_agent,
    user: Current.user
  )

  render json: serialized_blob(blob), status: :created
end
```

## Attachment Validation

```ruby
def validate_attachment(name, size, mime_type)
  return I18n.t("chatkit.errors.invalid_attachment_params") if name.blank? || size.to_i <= 0 || mime_type.blank?
  return I18n.t("chatkit.errors.attachment_too_large") if size.to_i > ChatkitConfig.upload_max_bytes

  allowed = ChatkitConfig.allowed_mime_types
  if allowed.any? && !allowed.include?(mime_type)
    return I18n.t("chatkit.errors.unsupported_mime_type")
  end

  nil
end
```

## Attachment Create (Pre-upload)

ChatKit's `attachments.create` prepares upload metadata:

```ruby
def handle_attachment_create(req)
  unless requested_agent
    return render(json: { error: I18n.t("chatkit.errors.agent_required") }, status: :unprocessable_content)
  end

  params_hash = req["params"] || {}
  name = params_hash["name"].to_s
  size = params_hash["size"].to_i
  mime_type = params_hash["mime_type"].to_s

  if (error = validate_attachment(name, size, mime_type))
    return render json: { error: error }, status: :unprocessable_content
  end

  # Create placeholder ID with metadata for validation during upload
  placeholder_id = Base64.urlsafe_encode64(
    { name: name, size: size, mime_type: mime_type, agent_id: requested_agent.id }.to_json,
    padding: false
  )

  render json: {
    id: placeholder_id,
    uploadUrl: chatkit_upload_url(agent_id: requested_agent.id),
    uploadHeaders: { "X-CSRF-Token" => form_authenticity_token },
    uploadStrategy: { type: "direct" },
    name: name,
    mimeType: mime_type
  }
end
```

## Attachment Delete

```ruby
def handle_attachment_delete(req)
  attachment_id = req.dig("params", "attachment_id")
  if attachment_id.blank?
    return render json: { error: I18n.t("chatkit.errors.attachment_id_required") }, status: :unprocessable_content
  end

  blob = ActiveStorage::Blob.find_signed(attachment_id)
  attachment_records = ChatkitAttachment.where(blob: blob, account: Current.account)
  attachment_records = attachment_records.where(agent: requested_agent) if requested_agent

  if attachment_records.none?
    return render json: { error: I18n.t("chatkit.errors.attachment_not_found") }, status: :not_found
  end

  attachment_records.delete_all
  blob.purge_later unless ChatkitAttachment.exists?(blob: blob)

  render json: {}
rescue ActiveSupport::MessageVerifier::InvalidSignature
  render json: { error: I18n.t("chatkit.errors.attachment_not_found") }, status: :not_found
end
```

## Attaching Blobs to Messages

```ruby
def attach_blobs(message, signed_ids)
  return if signed_ids.blank?

  blobs = blobs_for_ids(signed_ids)
  blobs.each { |blob| message.attachments.attach(blob) }
end

def blobs_for_ids(ids)
  ids.filter_map do |id|
    blob = begin
      ActiveStorage::Blob.find_signed(id)
    rescue ActiveSupport::MessageVerifier::InvalidSignature
      nil
    end
    next unless blob

    # Verify attachment is allowed for this account/agent
    scope = ChatkitAttachment.where(blob: blob, account: Current.account)
    scope = scope.where(agent: requested_agent) if requested_agent
    next unless scope.exists?

    blob
  end
end

def attachment_ids_from(attachments)
  Array(attachments).filter_map do |att|
    case att
    when Hash then att["id"] || att[:id]
    else att
    end
  end
end
```

## Serializing Attachments

```ruby
def serialized_attachments(message)
  return [] unless message.attachments.attached?

  message.attachments.map do |attachment|
    serialized_blob(attachment.blob, attachment)
  end
end

def serialized_blob(blob, attachment_record = nil)
  if blob.image?
    {
      id: blob.signed_id,
      type: "image",
      name: blob.filename.to_s,
      mimeType: blob.content_type,
      preview: url_for(attachment_record || blob)
    }
  else
    {
      id: blob.signed_id,
      type: "file",
      name: blob.filename.to_s,
      mimeType: blob.content_type
    }
  end
end
```

## Routes

```ruby
post "chatkit/upload" => "chatkit#upload", as: :chatkit_upload
```

## Configuration

```ruby
ChatkitConfig.upload_max_bytes      # Default: 25MB
ChatkitConfig.allowed_mime_types    # Array of allowed MIME types
```

Environment variables:
- `CHATKIT_UPLOAD_MAX_BYTES` - Maximum upload size in bytes
- `CHATKIT_ALLOWED_MIME_TYPES` - Comma-separated list of allowed types
