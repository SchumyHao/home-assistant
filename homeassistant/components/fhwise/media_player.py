"""The implementation of fhwise media player."""
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "fh wise media player"
DEFAULT_PORT = 8080

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA_BASE.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

ATTR_MODEL = "model"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the media player demo platform."""
    from fhwise import FhwisePlayer

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)
    model = ""

    _LOGGER.info(f"Initializing with {host}:{port}")

    try:
        fhPlayer = FhwisePlayer(host, port)
        fhPlayer.connect()
        model = fhPlayer.send_heartbeat()
        fhPlayer.disconnect()
        _LOGGER.info(f"{model} detected")
    except Exception:
        raise PlatformNotReady

    async_add_entities(
        [FhwiseMusicPlayer(fhPlayer, host, port, model, name)], update_before_add=True
    )


YOUTUBE_COVER_URL_FORMAT = "https://img.youtube.com/vi/{}/hqdefault.jpg"
SOUND_MODE_LIST = ["Dummy Music", "Dummy Movie"]
DEFAULT_SOUND_MODE = "Dummy Music"

YOUTUBE_PLAYER_SUPPORT = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SEEK
)

MUSIC_PLAYER_SUPPORT = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOUND_MODE
)

NETFLIX_PLAYER_SUPPORT = (
    SUPPORT_PAUSE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOUND_MODE
)


class AbstractFhwisePlayer(MediaPlayerDevice):
    """A fhwise media players."""

    def __init__(self, player, host, port, model, name, device_class=None):
        """Initialize the demo device."""
        self._player = player
        self._host = host
        self._port = port
        self._model = model
        self._name = name
        self._unique_id = f"{self._model}-{self._host}"

        self._state_attrs = {ATTR_MODEL: self._model}
        self._player_state = STATE_PLAYING
        self._volume_level = 1.0
        self._volume_muted = False
        self._shuffle = False
        self._sound_mode_list = SOUND_MODE_LIST
        self._sound_mode = DEFAULT_SOUND_MODE
        self._device_class = device_class
        self._available = False
        self._skip_update = False

    @property
    def should_poll(self):
        """Push an update after each command."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the media player."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def state(self):
        """Return the state of the player."""
        return self._player_state

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume_level * 0.0625

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._volume_muted

    @property
    def shuffle(self):
        """Boolean if shuffling is enabled."""
        return self._shuffle

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return self._sound_mode_list

    @property
    def device_class(self):
        """Return the device class of the media player."""
        return self._device_class

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a player command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug(f"Response received from player: {result}")

            return result
        except Exception:
            _LOGGER.error(mask_error)
            self._available = False
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the media player on."""
        if self._player_state is not STATE_PLAYING:
            result = await self._try_command(
                "Turning the player on failed.", self._player.send_play_pause
            )
            if result:
                self._state = STATE_PLAYING
                self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn the media player off."""
        if self._player_state is STATE_PLAYING:
            result = await self._try_command(
                "Turning the player off failed.", self._player.send_play_pause
            )
            if result:
                self._state = STATE_OFF
                self._skip_update = True

    async def mute_volume(self, mute, **kwargs):
        """Mute the volume."""
        if self._volume_muted is not mute:
            result = await self._try_command(
                "Mute the player failed.", self._player.set_volume_toggle_mute
            )
            if result:
                self._volume_muted = mute
                self._skip_update = True

    async def volume_up(self, **kwargs):
        """Increase volume."""
        vol = min(15, self._volume_level + 1)
        result = await self._try_command(
            "Set volume level failed.", self._player.set_volume_level, vol
        )
        if result:
            self._volume_level = vol
            self._skip_update = True

    async def volume_down(self):
        """Decrease volume."""
        vol = max(0, self._volume_level - 1)
        result = await self._try_command(
            "Set volume level failed.", self._player.set_volume_level, vol
        )
        if result:
            self._volume_level = vol
            self._skip_update = True

    async def set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        vol = int(volume / 0.0625)
        result = await self._try_command(
            "Set volume level failed.", self._player.set_volume_level, vol
        )
        if result:
            self._volume_level = vol
            self._skip_update = True

    async def media_play(self):
        """Send play command."""
        if self._player_state is not STATE_PLAYING:
            result = await self._try_command(
                "Turning the player on failed.", self._player.send_play_pause
            )
            if result:
                self._state = STATE_PLAYING
                self._skip_update = True

    async def media_pause(self):
        """Send pause command."""
        if self._player_state is STATE_PLAYING:
            result = await self._try_command(
                "Turning the player off failed.", self._player.send_play_pause
            )
            if result:
                self._state = STATE_OFF
                self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            play_state = await self._try_command(
                "Get play status failed.", self._player.get_play_status
            )
            _LOGGER.debug(f"Got new state: {play_state}")
            if play_state == 1:
                self._player_state = STATE_PLAYING
            else:
                self._player_state = STATE_PAUSED

            vol_level = await self._try_command(
                "Get volume level failed", self._player.get_volume_level
            )
            _LOGGER.debug(f"Got new vol level: {vol_level}")
            self._volume_level = vol_level
            if vol_level:
                self._volume_muted = True
            else:
                self._volume_muted = False

            self._available = True

        except Exception:
            self._available = False
            _LOGGER.error(f"Got exception while fetching the state")
            traceback.print_exc()  # noqa


'''
    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle
        self.schedule_update_ha_state()

    def select_sound_mode(self, sound_mode):
        """Select sound mode."""
        self._sound_mode = sound_mode
        self.schedule_update_ha_state()
'''


class FhwiseMusicPlayer(AbstractFhwisePlayer):
    """A fhwise media player that only supports music."""

    tracks = [
        ("Technohead", "I Wanna Be A Hippy (Flamman & Abraxas Radio Mix)"),
        ("Paul Elstak", "Luv U More"),
        ("Dune", "Hardcore Vibes"),
        ("Nakatomi", "Children Of The Night"),
        ("Party Animals", "Have You Ever Been Mellow? (Flamman & Abraxas Radio Mix)"),
        ("Rob G.*", "Ecstasy, You Got What I Need"),
        ("Lipstick", "I'm A Raver"),
        ("4 Tune Fairytales", "My Little Fantasy (Radio Edit)"),
        ("Prophet", "The Big Boys Don't Cry"),
        ("Lovechild", "All Out Of Love (DJ Weirdo & Sim Remix)"),
        ("Stingray & Sonic Driver", "Cold As Ice (El Bruto Remix)"),
        ("Highlander", "Hold Me Now (Bass-D & King Matthew Remix)"),
        ("Juggernaut", 'Ruffneck Rules Da Artcore Scene (12" Edit)'),
        ("Diss Reaction", "Jiiieehaaaa "),
        ("Flamman And Abraxas", "Good To Go (Radio Mix)"),
        ("Critical Mass", "Dancing Together"),
        (
            "Charly Lownoise & Mental Theo",
            "Ultimate Sex Track (Bass-D & King Matthew Remix)",
        ),
    ]

    def __init__(self, player, host, port, model, name):
        """Initialize the fhwise music player device."""
        super().__init__(player, host, port, model, name)
        self._cur_track = 0


'''
    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return "bounzz-1"

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return 213

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return "https://graph.facebook.com/v2.5/107771475912710/" "picture?type=large"

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self.tracks[self._cur_track][1] if self.tracks else ""

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        return self.tracks[self._cur_track][0] if self.tracks else ""

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return "Bounzz"

    @property
    def media_track(self):
        """Return the track number of current media (Music track only)."""
        return self._cur_track + 1

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return MUSIC_PLAYER_SUPPORT

    def media_previous_track(self):
        """Send previous track command."""
        if self._cur_track > 0:
            self._cur_track -= 1
            self.schedule_update_ha_state()

    def media_next_track(self):
        """Send next track command."""
        if self._cur_track < len(self.tracks) - 1:
            self._cur_track += 1
            self.schedule_update_ha_state()

    def clear_playlist(self):
        """Clear players playlist."""
        self.tracks = []
        self._cur_track = 0
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()
'''
