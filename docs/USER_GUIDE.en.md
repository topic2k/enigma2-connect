[Deutsch](BENUTZERHANDBUCH.md) | [English](USER_GUIDE.en.md)

# User guide

[Back to the short overview](../README.md#english)

Enigma2 Connect lets you control your receiver from Home Assistant: change
channels, adjust volume, play recordings on the TV and display messages. You can
also use these controls in automations. Video and audio play on the receiver and
its connected TV. Browser and Cast playback are not included.

## Contents

- [Install and set up](#install-and-set-up)
- [Control your receiver](#control-your-receiver)
- [Browse recordings and channels](#browse-recordings-and-channels)
- [Choose preview images](#choose-preview-images)
- [Change settings](#change-settings)
- [Dashboard remote](#dashboard-remote)
- [Messages and automations](#messages-and-automations)
  - [Actions and examples](#actions-and-examples)
- [Timers and calendar](#timers-and-calendar)
- [Troubleshooting](#troubleshooting)
- [Update or remove](#update-or-remove)

## Install and set up

You need Home Assistant **2026.9 or later** and an Enigma2 receiver with OpenWebif
enabled. OpenWebif is the receiver's web interface. Open it in a browser first
and check that you can control the receiver. Home Assistant must also be able
to reach this address.

Manual installation requires access to Home Assistant's configuration folder. Back up your Home
Assistant installation before installing.

1. Copy the project's entire `custom_components/enigma2_connect` folder to
   `/config/custom_components/enigma2_connect`. Create `custom_components` if it
   does not exist yet.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and search for
   **Enigma2 Connect**.
4. Enter the receiver's IP address or hostname, for example `192.168.1.50`.
   Leave out `http://`, the port and any path in this field.
5. Enter the OpenWebif port in its own field. Common values are **80** for HTTP
   and **443** for HTTPS; use the value configured on your receiver.
6. Enable HTTPS only if OpenWebif is configured for it. Leave username and
   password empty if OpenWebif does not require a login.
7. Complete the dialog and open the newly added device.

The connection fields also apply to **Reconfigure** and reauthentication:

| Field | Default and meaning |
| --- | --- |
| Hostname or IP address | No default; receiver address without scheme, port or path. |
| Port (HTTP: 80, HTTPS: 443) | Initially 80; for HTTPS, change it to the configured receiver port when necessary, usually 443. |
| Username | Empty; enter only when OpenWebif authentication is enabled. |
| Password | Empty; the password for OpenWebif authentication. |
| Use HTTPS | Off; enable only when OpenWebif supports and is configured for HTTPS. |
| Verify TLS certificate | On; checks whether the HTTPS receiver certificate is trusted. Verification can be disabled for a deliberately configured, untrusted private certificate. |

Add further receivers in the same way. Give them recognizable names, such as
“Living room” and “Bedroom”. Setup uses the interface throughout; no YAML
configuration is required.

### HACS

Add the [project repository](https://github.com/topic2k/enigma2-connect)
through HACS **Custom repositories**, with type **Integration**, then download it.
Restart Home Assistant and add the integration as described above. The
[HACS guide](https://www.hacs.xyz/docs/faq/custom_repositories/) explains the steps.
Inclusion in the default HACS catalog is not promised.

### Discover receivers and update addresses

If OpenWebif announces its web service through Bonjour with a name starting with
“OpenWebif”, it appears under **Settings → Devices & services**. Open **Add**, check
the prefilled address, port and HTTPS setting, provide credentials if required,
then complete the dialog. Pairing happens only after confirmation and API validation.
Without a matching Bonjour name, or when multicast is blocked, use manual setup
above. Installing OpenWebif alone does not guarantee a matching announcement;
the image and its Bonjour/Avahi configuration determine this.

For paired receivers, Home Assistant can adopt a new IP detected through DHCP.
The known MAC address must match the identity returned by OpenWebif. Port,
authentication and TLS settings are preserved. Another announcement never disables HTTPS.

If OpenWebif device information is missing after restarting the network interface,
restarting the receiver's user interface (Enigma2/GUI) may help. Choose a time with
no recording in progress. Once the known MAC is reported again, you can change
the address through **Reconfigure** if needed. For an entry paired by MAC, this
also remains blocked while its hardware identity is missing or different.

### Supported devices

The OpenWebif JSON API is required. Brand names or Enigma2 alone do not prove
compatibility. These existing checks took place on 13 September 2026 against
version 0.1.0. In addition, current read-only acceptance passed on the Octagon:
setup, entities, refresh, screenshot and picon. Additional checks covered recording
artwork, bounded control actions and address adoption after an actual DHCP change:

| Receiver / OpenWebif | Verified scope and limitation |
| --- | --- |
| Octagon SF8008 4K Supreme / 2.4.0 | Live TV/radio, recordings, picons/screenshots, remote controls, messages, timers, standby and restart were checked. |
| Vu+ Solo² / 1.4.4 | Setup without authentication, separate devices, catalogs, remote controls, messages and timers were checked. No second video/audio acceptance because the DVB input signal was missing. |
| Other Enigma2 receivers / images | May work with a compatible OpenWebif API; no specific hardware evidence yet. Optional data may be absent. |
| Receivers without the OpenWebif JSON API | Unsupported; an HTML web interface alone is insufficient. |

New discovery and address updates have been tested with explicitly triggered
announcements and real HA configuration flows, including the Octagon's new IP.
Automatic discovery of actual network announcements remains pending.
See the [validation overview](VALIDATION.en.md#current-read-only-octagon-acceptance)
for the precise hardware scope.

## Control your receiver

Find your receivers under **Settings → Devices & services → Enigma2 Connect**.
Open a device to see its controls and information. Home Assistant calls these
individual items “entities”.

| Item | Use it to … |
| --- | --- |
| Media player | turn power on/off, adjust volume, mute and control playback |
| Bouquet and channel selection | choose a channel group, then a channel |
| Receiver control | switch normal standby and use the remote card |
| Screen message | display text on the TV |
| Channel and programme information | view the current and next programme |
| Status indicators | check connection, standby, recording and streaming |
| Signal values and counters | view reception readings and recording/timer counts |
| Camera | view a screenshot from the receiver |
| Calendar | view receiver timers |
| Refresh lists | fetch channels, timers and recordings again |

Add the **media player** to your dashboard. Select a channel under **Source**.
A channel group is called a “bouquet” in Enigma2; use it to switch between groups
such as TV favorites and radio channels.

Turning off normally uses **standby**, from which the receiver can be switched
on again. **Deep standby** shuts it down; the integration cannot wake it from
that state. The **Receiver control** switch always uses normal standby, even if
the media player's power-off option is set to deep standby.

Play, pause and stop send the respective command. The receiver does not reliably
report whether playback is paused, so check the TV for that. Some dashboard cards
do not show stop; the [remote card](#dashboard-remote) provides additional buttons.
Further individual button entities are disabled by default and can be enabled
in their entity settings if needed.

Signal quality, SNR and reported bit error rate are optional diagnostics and
initially disabled for new entities. Open **Settings → Devices & services →
Entities**, show disabled entities and enable the sensor you need. Existing
enable/disable choices are preserved on upgrades. Receiver states also cover
standby, recording, streaming and connectivity; connectivity and **Refresh lists**
are diagnostics.

## Browse recordings and channels

There are two ways to find recordings:

- Open **Browse media** on the media player for that receiver's recordings.
- Open **Media → Enigma2 recordings** in the sidebar to choose between all your
  configured receivers.

Open the required subfolders and select a recording. In the Media sidebar,
select the receiver that holds the recording as the player at the bottom.
If you choose “Web browser” or another device, Home Assistant names the receiver
you need instead.

Titles include the date, time, channel and duration when available. Times use
Home Assistant's configured time zone. Folders appear before recordings. The
list reflects what OpenWebif reports from the recording directory and its subfolders.

### Show multiple receivers together

Open the [receiver options](#change-settings) and set **Recordings in the media
tile** to **Combine receivers**. This applies to all receivers. Folders with the
same name appear together, and each recording includes its receiver's name.
Recordings with matching names remain separate entries.

### Also show channels in the media browser

By default, the media browser contains recordings only. Enable **Show channels
in the media browser** in the options to add a **Channels** folder. **Bouquet for
the media browser** chooses its channel group. Leave it empty to follow the
currently selected group. A separate selection here does not change the group
under **Source**.

These options apply per receiver and affect both media views. When recordings
are combined, the channel folder first lists receivers and then their channels.
Select the matching receiver as the player here too. Channel logos load from the
receiver; a TV symbol appears when a logo is missing.

## Choose preview images

In the receiver options, **Recording thumbnails – image sources** determines which
images appear. You can select several sources. Clear every selection to turn
preview images off.

### A frame from the recording

The default is **Snapshot from recording**: a single frame ten minutes into the
recording file, including any recording pre-roll. Change the position separately
for each receiver. Shorter completed recordings use their midpoint. For a
recording still in progress, extraction waits until the selected position is available.

Images are prepared in the background, newest recordings first. You do not need
to open the media browser. In large collections, older images are created when
requested. Preparation can take time and does not start playback on the TV.
OpenWebif must allow reading the recording file. See
[Troubleshooting](#troubleshooting) if images are missing.

### Movie and TV images from the internet

Select **TMDB** or **OMDb (IMDb association)** as additional sources and enter
each provider's API key. This is the provider's access key, not your receiver
password. Obtain it from
[TMDB](https://developer.themoviedb.org/docs/getting-started) or
[OMDb](https://www.omdbapi.com/apikey.aspx).

Only selected providers are queried. They receive the recording title, including
during background preparation. OMDb is a separate service with an IMDb
association; it does not search the IMDb website directly. Matching or imprecise
titles can lead to an unsuitable image.

### Your own image address

Use **Custom image URL** for an image from your own image service. Enter a direct
address to a JPEG, PNG or WebP file. A normal webpage or an address that redirects
does not work.

The address may contain these placeholders:

| Placeholder | Replaced with … |
| --- | --- |
| `{title}` | the recording title |
| `{filename}` | the filename without folders |
| `{channel}` | the channel name |

Example: `https://images.example/{title}.jpg`. These inserted values are sent to
your image service. Use an address without an embedded username or password.
A fixed image address without placeholders also works.

When several sources are selected, the order is **custom URL → TMDB → OMDb →
snapshot**. Once an image is found, later sources are not queried. If none supplies
an image, a neutral symbol remains; the recording is still playable. Images are
cached, and changed image settings trigger new images.

## Change settings

Open **Settings → Devices & services → Enigma2 Connect**, then **Configure**
for your receiver. The **Receiver options** menu has two choices:

- **Receiver settings**: view, change and save settings.
- **Regenerate thumbnails**: create images again using the saved image sources.

### Receiver settings

Most defaults can be left as they are. The bouquet dropdown shows your channel
group names. **—** means that no separate group is configured.

| Setting | Default and meaning |
| --- | --- |
| Recordings in the media tile (applies to all receivers) | Separate receivers; optionally combine them. This choice is saved for all receivers. |
| Polling interval (seconds) | 15 seconds; adjustable from 5 to 300 seconds. Smaller values refresh status more often. |
| Show channels in the media browser | Off; adds a channel folder to both media views. |
| Bouquet for the media browser | Empty; follows the group selected under Source. A separate choice does not change the media player's source. |
| Recording thumbnails – image sources | Snapshot only; select several sources if needed. Clear all selections to disable thumbnails. |
| Snapshot position after recording start | 10 minutes; 0–1440 minutes in 0.1-minute steps. Includes any pre-roll in the recording file. |
| TMDB API key | Empty; required when TMDB is selected as an image source. |
| OMDb API key | Empty; required when OMDb is selected as an image source. |
| Custom image URL | Empty; enter a direct image address for the “Custom image URL” source. |
| Default bouquet (optional) | Empty; initially uses the first group returned when loading. Select a group to make it the starting group. |
| Receiver timezone | Initially the HA time zone, for example `Europe/Berlin`. Important for recurring timers. |
| Media artwork | Channel logo; alternatively screenshot or no image. Affects the media player, not recording thumbnails. |
| Message duration (seconds) | 10 seconds; 1–120 seconds for screen messages sent through `notify.send_message`. |
| Message type (0–3) | 1: information. Also 0: yes/no question, 2: warning, 3: error. Applies to `notify.send_message`; presentation depends on the receiver. |
| Power-off mode | Standby; alternatively deep standby. Affects the media player. The integration cannot wake the receiver from deep standby. |

Except for the shared recording layout, settings apply only to the chosen receiver.
See [Choose preview images](#choose-preview-images) for image sources, access keys
and address placeholders. Save your changes at the end of the form.

### Regenerate thumbnails

1. To use different images, first select the sources you want under
   **Receiver settings** and save them.
2. Reopen receiver options and select **Regenerate thumbnails**.
   Preparation starts immediately for this receiver.
3. Allow some time, then reopen the media list to see the new images.

Media browsing remains available. Newer recordings are prepared in the background;
older recordings receive a new image on their next request. Saved settings and
other receivers' images are preserved. You can repeat regeneration when needed.
If all image sources are disabled, nothing starts: select and save at least one
source first.

### Connection and refresh

**Reconfigure** changes the address, port, login and HTTPS settings. Certificate
verification can be disabled for a private HTTPS certificate that is not trusted.
Rejected credentials prompt Home Assistant to request a new login.

A bouquet changed during use remains selected until the integration reloads.
Save a preferred starting group in the options. Timers and recordings normally
refresh every two minutes; channel catalogs every five minutes. Use **Refresh
lists** for an immediate update.
The action waits for its fetch and reports an error if the receiver could not be
updated. Even immediately repeated calls perform a new fetch instead of using
the previous result.

When the receiver cannot be reached, its controls become **Unavailable**. The
connection indicator remains visible and shows the loss of connection. Missing
individual optional values may appear as **Unknown**; an inaccessible timer
catalog makes the calendar unavailable. The integration retries automatically.
Failure and recovery are logged once each, not on every retry.

States are polled locally, every 15 seconds by default. Between polls, the
display may lag behind receiver controls. Relevant actions also request an update.
Recordings and timers follow their two-minute cadence, channel catalogs five minutes.
Recording images are prepared in the background at setup and on catalog updates:
at most 128 recent images, one job at a time with at least a five-second pause.
Older images are generated on demand. Local images expire after seven days;
the browser may reuse recording images for one day and channel logos for
15 minutes. Screenshots are reused for at most five seconds. **Regenerate thumbnails**
bypasses the recording-image cache.

## Dashboard remote

Install the remote card separately from the integration:

1. Copy `www/enigma2-connect-remote-card.js` to
   `/config/www/enigma2-connect-remote-card.js`. If you create `www` for the
   first time, restart Home Assistant afterwards.
2. Open your dashboard resource settings and add
   `/local/enigma2-connect-remote-card.js` as a **JavaScript module**. The
   [HA resource guide](https://developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/)
   helps you find the settings page.
3. Edit your dashboard. Under **Add card → By card**, search for **Enigma2** and
   select **Enigma2 Connect Remote**.
4. Select the desired receiver's **Receiver control** in the card editor.
   Optionally give it a name such as “Living room”.

Arrow, volume, channel and seek buttons support holding. The card needs no
separate receiver login. Errors appear directly on the card.

For a card update, replace the file and change the existing resource entry, for
example to `/local/enigma2-connect-remote-card.js?v=2`. Fully reload the browser.
Do not add a second resource entry. A card-only update needs no HA restart.

The optional card also supports manual configuration:

```yaml
type: custom:enigma2-connect-remote-card
entity: remote.test_receiver_remote
name: Living room
```

## Messages and automations

First try a screen message under **Developer tools → Actions**: choose
**Notifications: Send a message** (`notify.send_message`), target your receiver's
**Screen message** entity and enter some text. A title is optional.

To show a message when the doorbell rings:

1. Create an automation under **Settings → Automations & scenes**.
2. Choose your doorbell's activation as the trigger.
3. Add **Send a message** as an action.
4. Target the receiver's screen message entity.
5. Enter a message such as “Someone is at the door” and save the automation.

For a different message type or duration, use the **Enigma2 Connect** message
action and select the receiver device. Answers to yes/no questions are not
currently returned to Home Assistant.

Channel changes, standby and button sequences can also be automated.
The examples below show you the matching actions.

The integration provides no custom triggers or conditions. Use the standard
Home Assistant state triggers and conditions in automations, for example a
change of the recording or connection indicator.

### Actions and examples

Use these examples for your own scripts and automations. Try them in YAML
mode under **Developer tools → Actions**, or insert them as an individual
action in an automation. YAML is the text view of the settings. These
examples do not include a trigger.

Replace the example entities with your own targets. For a device action,
select the receiver in the interface first; switch to YAML to see its
`device_id`. Change channel references and dates as needed too.

| Action | Target and data |
| --- | --- |
| `remote.send_command` | Remote entity; `command`, optionally `delay_secs`, `num_repeats`, `hold_secs` |
| `media_player.play_media` | Media player; `channel` for a number, `enigma2_reference` for a service reference, `enigma2_recording` for a recording reference |
| `media_player.media_play`, `.media_pause`, `.media_stop` | Media player; playback buttons without reliable pause feedback |
| `notify.send_message` | Screen message entity; `message`, optional `title`. Uses the message type and duration from receiver settings. |
| `enigma2_connect.message` | `device_id`, `text`, optional `type` (0–3, default 1) and `timeout` (1–120 seconds, default 10) |
| `enigma2_connect.reboot`, `.restart_gui`, `.deep_standby` | `device_id`; receiver restart, GUI restart or deep standby |
| `enigma2_connect.timer_add` | `device_id`, `service_reference`, `begin`, `end`, `name`; optional `description`, `justplay`, `afterevent` |
| `enigma2_connect.timer_delete`, `.timer_toggle` | `device_id`, `service_reference`, `begin`, `end` of the existing timer |

Always select the intended receiver as the target. Names starting with a dot
in the table share the beginning of the first action in that row.
For button sequences, use names such as `menu`, `up`, `down` and `ok`.
`delay_secs` is the pause between presses in seconds; `num_repeats` repeats
the sequence. A `hold_secs` value greater than 0 sends a long press; its
actual duration depends on the receiver.

Enter timer start and end values with a date, time and time zone as shown in the
example. Its `+02:00` means German summer time; adjust it to your date and location.
With `justplay: true`, the receiver switches to the channel without recording.
`afterevent` controls what happens afterwards: 0 = nothing, 1 = standby,
2 = deep standby, 3 = automatic. To delete or enable/disable a timer, use its
channel reference and original start and end values. For recurring timers, the
change affects the whole series. Lists refresh after the action.

#### Send a button sequence

```yaml
action: remote.send_command
target:
  entity_id: remote.test_receiver_remote
data:
  command: [menu, down, down, ok]
  delay_secs: 0.3
  num_repeats: 1
```

#### Select a channel by number

```yaml
action: media_player.play_media
target:
  entity_id: media_player.test_receiver
data:
  media_content_type: channel
  media_content_id: "105"
```

#### Display a message on the TV

```yaml
action: notify.send_message
target:
  entity_id: notify.test_receiver_screen_message
data:
  title: Doorbell
  message: Someone is at the door.
```

#### Create a single recording timer

```yaml
action: enigma2_connect.timer_add
data:
  device_id: YOUR_RECEIVER_DEVICE_ID
  service_reference: "1:0:1:6DD2:44D:1:C00000:0:0:0:"
  begin: "2026-10-10T20:15:00+02:00"
  end: "2026-10-10T21:45:00+02:00"
  name: Film
  description: Recording from Home Assistant
  justplay: false
  afterevent: 3
```

## Timers and calendar

The calendar shows recording and channel-switch timers from the receiver,
including weekly repeats. You can view them there but cannot edit them directly.

To create a single timer, open **Developer tools → Actions → Enigma2 Connect:
Add timer**. Select the receiver and enter a name, start/end times and the channel
identifier from OpenWebif. This **service reference** is different from a channel
number. The [action reference](#actions-and-examples) includes
an example with all fields. Enable **Zap only** for a channel-switch timer.

Deleting or enabling/disabling timers also uses Enigma2 Connect actions. For a
recurring timer, changes affect the whole series. Create new series or edit
individual occurrences directly in OpenWebif or on the receiver. At daylight-saving
changes, check the receiver time zone and verify the schedule on the receiver too.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Cannot find the integration | Check the copied folder and restart Home Assistant. Receivers are not discovered automatically. |
| Connection fails | Open OpenWebif in a browser; check address, port, login and HTTPS through **Reconfigure**. Old interfaces without OpenWebif are not supported. |
| Receiver is “Unavailable” | Check network and power. Deep standby usually makes it unreachable; normal standby is a different state. |
| New recordings or channels are missing | Press **Refresh lists**. If entries remain missing, check the corresponding list in OpenWebif. |
| Recording will not play | Select the receiver holding it in the Media sidebar. “Web browser” and Cast devices cannot play it. |
| Preview is missing | Check sources and keys and allow time for preparation. For an ongoing recording, the chosen position must first become available. Frames require FFmpeg on the HA system and readable recording files; technical details are in the developer guide. |
| Poster is wrong | The title search may find a different result. Use a snapshot or custom image address instead. |
| Channel logo is missing | Matching logos must exist on the receiver; otherwise a placeholder is shown. |
| Screenshot briefly appears black | The receiver needs time to build the picture after a channel change. Try again later. |
| Play/pause indicator seems wrong | The receiver does not reliably report pause state. Check the TV. |
| Card is missing or outdated | Check the resource address, module type and selected receiver control; fully reload the browser after updating. |
| Signal values or counts are unknown | The receiver may not supply suitable values, or a list request failed. Later refreshes retry. |

Restart, GUI restart or deep standby may disconnect the receiver before Home
Assistant receives confirmation. The command may still have arrived. Check the
receiver before sending again; a confirmation prompt may also be open on the TV.
An unknown **Screen message** state before its first message is not a connection error.

For further help, report your steps, expected and actual behavior, HA version,
receiver model and OpenWebif version in the
[issue tracker](https://github.com/topic2k/enigma2-connect/issues). Download a
diagnostics export under **Devices & services** if possible. It contains request
status and counts, not credentials, network addresses, channel names or recording titles.

The interface supports German and English. The remote follows your profile
language; the recordings tile and automatically assigned entity names follow the
HA system language. Other languages fall back to English. Custom names and
receiver text are not translated.

### FFmpeg repair issue

**FFmpeg is missing for recording thumbnails** means the selected snapshot source
cannot find an executable FFmpeg. Install it in the Home Assistant runtime or
correct the configured executable path, then reload Enigma2 Connect. Alternatively,
deselect **Snapshot from recording** in Receiver settings and save. This clears
the issue. Receiver controls and media catalogs remain usable. Removing a receiver
entry also removes its repair issue.

## Update or remove

Create an HA backup and read the [changelog](../CHANGELOG.en.md) before updating.
For manual installations, replace the component folder with the new version and
restart Home Assistant. Update the remote card separately as described above.

To remove the integration, delete its entry under **Devices & services**. You can
then remove the component folder and separately configured card resource.
Recordings and timers on the receiver remain intact.
