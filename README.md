<div align="center">

<img src="assets/icon.png" width="96" alt="">

# Untrack Show

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

Open the **⋮** menu of a show, season or episode and pick **Untrack show**. On a phone, long-press the card, tap **⋮**
at the top right, then **Untrack show**. Select several cards to untrack several shows at once.

<img src="docs/images/mobile.png" width="320" alt="Untrack show in the phone's multi-select menu">

Untracking marks every episode of the show unwatched, for you only. To bring the show back, play any episode. Tools
that delete unwatched media will treat an untracked show as unwatched.

It works in web browsers, the desktop app and the official Android and iOS apps. Native TV apps (Android TV, Fire TV,
Swiftfin, Roku) don't show the option, but a show you untrack elsewhere disappears there too.

## Manual install

Unzip `untrack-show.zip` from the [latest release](https://github.com/bmuraykhi/jellyfin-plugin-untrack/releases/latest)
into an `Untrack Show_<version>` folder in Jellyfin's plugins folder (`/var/lib/jellyfin/plugins` on Linux,
`/config/plugins` in Docker) and restart. To build it yourself with the .NET 10 SDK, run
`dotnet publish -c Release -o bin/publish` and use the DLL with `meta.json` and `assets/icon.png`.

## License

The source is under [The Unlicense](LICENSE). The built plugin links against Jellyfin's GPL-3.0 libraries, so the
released DLL and zip are under the GPL-3.0.
