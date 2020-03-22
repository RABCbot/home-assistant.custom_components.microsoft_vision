# Home-Assistant-MicrosoftVision
This custom integration calls the Microsoft Azure Cognitive services Vision API https://azure.microsoft.com/en-us/services/cognitive-services/#api

## Setup
You will need the API endpoint and key from your Azure account

## Installation
Copy all the files to your custom_component folder

## Configuration
Add to your configuration yaml:

```yaml
image_processing:
  - platform: microsoft_vision
    api_key: <your api key?
    url: <your endpoint?
```

## Sample script
```yaml
vision:
  alias: Vision
  sequence:
  - service: image_processing.snapshot
    data:
      camera_entity: camera.door
  - service: image_processing.describe
  - service: notify.notifyme
    data_template:
      message: With "{{ states.image_processing.microsoft_vision.attributes.confidence
        }}" percent confidence, I see "{{ states.image_processing.microsoft_vision.attributes.description
        }}"
```
