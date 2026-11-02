<div align="center">

<img src="assets/icon.png" width="480" alt="Untrack Show">

Remove a whole show from Continue Watching and Next Up in one click.

[![Latest release](https://img.shields.io/github/v/release/bmuraykhi/jellyfin-plugin-untrack?label=release&color=AA5CC3)](https://github.com/bmuraykhi/jellyfin-plugin-untrack/releases/latest)
[![CI](https://github.com/bmuraykhi/jellyfin-plugin-untrack/actions/workflows/ci.yml/badge.svg)](https://github.com/bmuraykhi/jellyfin-plugin-untrack/actions/workflows/ci.yml)

</div>

![Untracking a show from the home screen](docs/images/demo.gif)

## Install

You need Jellyfin 12.4 and the
[File Transformation](https://github.com/IAmParadox27/jellyfin-plugin-file-transformation) plugin. To get File
Transformation, add its catalog the same way as in step 1 and install it from there:

```
https://www.iamparadox.dev/jellyfin/plugins/manifest.json
```

1. Dashboard → **Plugins** → **Manage Repositories** → **+**, and add

   ```
   https://raw.githubusercontent.com/bmuraykhi/jellyfin-plugins/main/manifest.json
   ```

2. **Catalog** → **Untrack Show** → **Install**
3. Restart Jellyfin, then reload the page or reopen the app.

## Use

Open the **⋮** menu of a show, season or episode and pick **Untrack show**.

Untracking marks every episode of the show unwatched, for you only. To bring the show back, play any episode. Tools
that delete unwatched media will treat an untracked show as unwatched.

It works in web browsers and the Jellyfin desktop app. Other apps don't show the option, but a show you untrack
disappears from them too.

## How it works

- File Transformation adds one `<script>` tag to Jellyfin's web page as it's served, and the plugin serves that script
  at `/UntrackShow/script`. No jellyfin-web files are changed.
- The script adds **Untrack show** to the ⋮ menus. Picking it asks Jellyfin to mark the whole show unplayed for you
  (`DELETE /UserPlayedItems/{showId}`), then reloads the page so the home rows update.
- It has no settings, stores nothing and only talks to your Jellyfin server.

## License

The source is under [The Unlicense](LICENSE). The built plugin links against Jellyfin's GPL-3.0 libraries, so the
released DLL and zip are under the GPL-3.0.
