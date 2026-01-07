# ChatKit UI Components

Available components for building widgets.

## Layout Components

### Card

Container for widget content:

```json
{
  "type": "Card",
  "theme": "dark",
  "size": "sm",
  "padding": { "y": 8, "x": 4 },
  "background": "linear-gradient(111deg, #1769C8 0%, #31A3F8 100%)",
  "children": [...]
}
```

Properties:
- `theme`: "light" | "dark"
- `size`: "sm" | "md" | "lg"
- `padding`: `{ x: number, y: number }` or number
- `background`: CSS gradient or color
- `children`: Array of child components

### Row

Horizontal layout:

```json
{
  "type": "Row",
  "align": "center",
  "gap": 2,
  "children": [...]
}
```

Properties:
- `align`: "start" | "center" | "end"
- `gap`: Spacing between children (number)
- `children`: Array of components

### Col

Vertical layout:

```json
{
  "type": "Col",
  "align": "center",
  "gap": 4,
  "children": [...]
}
```

Properties:
- `align`: "start" | "center" | "end"
- `gap`: Spacing between children (number)
- `children`: Array of components

## Text Components

### Text

General purpose text:

```json
{
  "type": "Text",
  "value": "Weather in Toronto",
  "size": "lg",
  "weight": "semibold",
  "color": "white",
  "textAlign": "center"
}
```

Properties:
- `value`: Text content
- `size`: "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl"
- `weight`: "normal" | "medium" | "semibold" | "bold"
- `color`: "primary" | "secondary" | "white" | CSS color
- `textAlign`: "left" | "center" | "right"

### Title

Large heading text:

```json
{
  "type": "Title",
  "value": "72°",
  "size": "3xl",
  "weight": "normal",
  "color": "white"
}
```

### Caption

Small secondary text:

```json
{
  "type": "Caption",
  "value": "San Francisco",
  "color": "white",
  "size": "lg"
}
```

## Media Components

### Image

Display image:

```json
{
  "type": "Image",
  "src": "https://openweathermap.org/img/wn/01d@2x.png",
  "size": 80
}
```

Properties:
- `src`: Image URL
- `size`: Width/height in pixels

## Interactive Components

### Button

Clickable button:

```json
{
  "type": "Button",
  "label": "Submit",
  "action": {
    "type": "custom_action",
    "payload": { "action": "submit" }
  }
}
```

### Select

Dropdown selection:

```json
{
  "type": "Select",
  "id": "audience",
  "label": "Target Audience",
  "options": [
    { "label": "Developers", "value": "developers" },
    { "label": "Designers", "value": "designers" }
  ],
  "required": true
}
```

## Complete Weather Widget Example

```json
{
  "type": "Card",
  "theme": "dark",
  "size": "sm",
  "padding": { "y": 8, "x": 4 },
  "background": "linear-gradient(111deg, #1769C8 0%, #258AE3 56.92%, #31A3F8 100%)",
  "children": [
    {
      "type": "Col",
      "align": "center",
      "gap": 2,
      "children": [
        {
          "type": "Row",
          "align": "center",
          "gap": 2,
          "children": [
            {
              "type": "Image",
              "src": "https://cdn.openai.com/API/storybook/mostly-sunny.png",
              "size": 80
            },
            {
              "type": "Title",
              "value": "72°",
              "size": "3xl",
              "weight": "normal",
              "color": "white"
            }
          ]
        },
        {
          "type": "Col",
          "align": "center",
          "gap": 4,
          "children": [
            {
              "type": "Caption",
              "value": "San Francisco",
              "color": "white",
              "size": "lg"
            },
            {
              "type": "Text",
              "value": "Sunny sky and warm temperatures expected.",
              "color": "white",
              "textAlign": "center"
            }
          ]
        }
      ]
    }
  ]
}
```

## Simple Card Example

```json
{
  "type": "Card",
  "children": [
    {
      "type": "Text",
      "value": "Weather in Toronto",
      "weight": "semibold",
      "size": "lg"
    },
    {
      "type": "Text",
      "value": "72°F",
      "size": "xl",
      "weight": "bold"
    },
    {
      "type": "Text",
      "value": "Sunny",
      "color": "secondary"
    }
  ]
}
```

## Form Widget Example

For human-in-the-loop interactions:

```json
{
  "type": "Card",
  "children": [
    {
      "type": "Text",
      "value": "Please answer the following questions:",
      "weight": "semibold"
    },
    {
      "type": "Select",
      "id": "audience",
      "label": "Target Audience",
      "options": [
        { "label": "Technical", "value": "technical" },
        { "label": "Non-technical", "value": "non-technical" }
      ],
      "required": true
    },
    {
      "type": "Select",
      "id": "tone",
      "label": "Writing Tone",
      "options": [
        { "label": "Formal", "value": "formal" },
        { "label": "Casual", "value": "casual" }
      ],
      "required": true
    },
    {
      "type": "Row",
      "gap": 2,
      "children": [
        {
          "type": "Button",
          "label": "Submit",
          "action": { "type": "human.form_submit" }
        },
        {
          "type": "Button",
          "label": "Cancel",
          "action": { "type": "human.cancel" }
        }
      ]
    }
  ]
}
```
