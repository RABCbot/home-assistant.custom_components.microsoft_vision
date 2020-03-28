import asyncio
import logging
import requests
import json
import time
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.entity import Entity
from homeassistant.components.image_processing import DOMAIN
from homeassistant.const import CONF_NAME, CONF_API_KEY, CONF_URL, CONF_TIMEOUT, ATTR_NAME, ATTR_ENTITY_ID, HTTP_BAD_REQUEST, HTTP_OK, HTTP_UNAUTHORIZED
from homeassistant.components.microsoft_face import CONF_AZURE_REGION, ATTR_CAMERA_ENTITY
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

MICROSOFT_VISION = 'microsoft_vision'

URL_VISION = "{0}/vision/v2.0/{1}"
SERVICE_ANALYZE = 'analyze'
SERVICE_DESCRIBE = 'describe'
SERVICE_DETECT = 'detect'
SERVICE_RECOGNIZE_TEXT = 'recognize_text'
SERVICE_SNAPSHOT = 'snapshot'

CONF_ENDPOINT = "endpoint"
CONF_VISUAL_FEATURES = 'visual_features'
CONF_RECOGNIZE_TEXT_MODE = 'mode'
CONF_VISUAL_FEATURES_DEFAULT = 'Brands,Description,Faces'
CONF_RECOGNIZE_TEXT_MODE_DEFAULT = 'Printed'

ATTR_DESCRIPTION = 'description'
ATTR_JSON = 'json'
ATTR_CONFIDENCE = 'confidence'
ATTR_BRAND = 'brand'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_ENDPOINT): cv.string,
        vol.Optional(CONF_VISUAL_FEATURES, default=CONF_VISUAL_FEATURES_DEFAULT): cv.string,
        vol.Optional(CONF_RECOGNIZE_TEXT_MODE, default=CONF_RECOGNIZE_TEXT_MODE_DEFAULT): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

SCHEMA_CALL_SERVICE = vol.Schema({
    vol.Required(ATTR_CAMERA_ENTITY): cv.string,
})

async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the platform."""
    if MICROSOFT_VISION not in hass.data:
        hass.data[MICROSOFT_VISION] = None

    devices = []
    try:
        device = MicrosoftVisionDevice(
            config.get(CONF_ENDPOINT), 
            config.get(CONF_API_KEY),
            config.get(CONF_VISUAL_FEATURES, CONF_VISUAL_FEATURES_DEFAULT),
            config.get(CONF_RECOGNIZE_TEXT_MODE, CONF_RECOGNIZE_TEXT_MODE_DEFAULT))
        devices.append(device)
        hass.data[MICROSOFT_VISION] = device
        add_devices(devices)
    except HomeAssistantError as err:
        _LOGGER.error("Error calling setup: %s", err)

    async def analize(service):
        device = hass.data[MICROSOFT_VISION]
        try:
            device.call_api(SERVICE_ANALYZE)
        except HomeAssistantError as err:
            _LOGGER.error("Error calling analyze: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_ANALYZE, analize)

    async def describe(service):
        device = hass.data[MICROSOFT_VISION]
        try:
            device.call_api(SERVICE_DESCRIBE)
        except HomeAssistantError as err:
            _LOGGER.error("Error calling describe: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_DESCRIBE, describe)

    async def detect(service):
        device = hass.data[MICROSOFT_VISION]
        try:
            device.call_api(SERVICE_DETECT)
        except HomeAssistantError as err:
            _LOGGER.error("Error calling detect: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_DETECT, detect)

    async def recognize_text(service):
        device = hass.data[MICROSOFT_VISION]
        try:
            device.call_api(SERVICE_RECOGNIZE_TEXT)
        except HomeAssistantError as err:
            _LOGGER.error("Error calling recognize text: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_RECOGNIZE_TEXT, recognize_text)

    async def snapshot(service):
        camera_entity = service.data.get(ATTR_CAMERA_ENTITY)
        camera = hass.components.camera
        device = hass.data[MICROSOFT_VISION]
        image = None
        try:
            image = await camera.async_get_image(camera_entity)
            device.set_image(image)
        except HomeAssistantError as err:
            _LOGGER.error("Error on receive image from entity: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_SNAPSHOT, snapshot, schema=SCHEMA_CALL_SERVICE)

    return True

class MicrosoftVisionDevice(Entity):
    """Representation of a platform."""

    def __init__(self, endpoint, api_key, visual_features=None, text_mode=None):
        """Initialize the platform."""
        self._state = None
        self._name = MICROSOFT_VISION
        self._api_key = api_key
        self._endpoint = endpoint
        self._description = None
        self._brand = None
        self._json = None
        self._image = None
        self._confidence = None
        self._visual_features = visual_features
        self._text_mode = text_mode

    @property
    def name(self):
        """Return the name of the platform."""
        return self._name

    @property
    def description(self):
        """Return the description of the platform."""
        return self._description

    @property
    def brand(self):
        """Return the brand of the platform."""
        return self._brand

    @property
    def json(self):
        """Return the JSON of the platform."""
        return self._json

    @property
    def confidence(self):
        """Return the confidence of the platform."""
        return self._confidence

    @property
    def state(self):
        """Return the state of the platform."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_DESCRIPTION: self._description,
            ATTR_BRAND: self._brand,
            ATTR_JSON: self._json,
            ATTR_CONFIDENCE: self._confidence
        }
        return attrs

    def call_api(self, service):
        try:
            url = URL_VISION.format(self._endpoint, service)

            headers = {"Ocp-Apim-Subscription-Key": self._api_key,
                       "Content-Type": "application/octet-stream"}
            params = None
            if service == SERVICE_ANALYZE:
                params =  {"visualFeatures": self._visual_features}
            if service == SERVICE_RECOGNIZE_TEXT:
                params =  {"mode": self._mode}

            self._json = None
            self._description = None
            self._brand = None
            self._confidence = None
            self.async_schedule_update_ha_state()

            response = requests.post(url, headers=headers, params=params, data=self._image.content)
            response.raise_for_status()
            self._json = response.json()
            
            if "description" in self._json:
                self._description = self._json["description"]["captions"][0]["text"]
                self._confidence = round(100 * self._json["description"]["captions"][0]["confidence"])
            if 'brands' in self._json and len(self._json["brands"]) != 0:
                self._brand = self._json["brands"][0]["name"]

            if response.status_code == 202:
                url = response.headers["Operation-Location"]
                time.sleep(4)
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                self._description = None
                self._json = response.json()

                if self._json["status"] == "Succeeded":
                    for line in self._json["recognitionResult"]["lines"]:
                        if line["text"] != "888":
                            self._description = line["text"]

            self.async_schedule_update_ha_state()

        except Exception as err:
            _LOGGER.error("Failed to call Microsoft API with error: %s", err)

    def set_image(self, image):
        self._image = image
