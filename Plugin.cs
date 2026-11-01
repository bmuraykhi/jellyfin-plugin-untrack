using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Controller.Configuration;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;

namespace Jellyfin.Plugin.UntrackShow;

/// <summary>
/// Adds "Untrack show" to the web client's item menu. It marks the whole show unplayed for the
/// current user, which removes it from Continue Watching and Next Up.
/// </summary>
public class Plugin : BasePlugin<BasePluginConfiguration>
{
    public Plugin(IApplicationPaths applicationPaths, IXmlSerializer xmlSerializer, IServerConfigurationManager serverConfigurationManager)
        : base(applicationPaths, xmlSerializer)
    {
        Instance = this;
        ServerConfigurationManager = serverConfigurationManager;
    }

    public static Plugin? Instance { get; private set; }

    public IServerConfigurationManager ServerConfigurationManager { get; }

    public override string Name => "Untrack Show";

    public override Guid Id => Guid.Parse("b54dbd71-0824-420d-974c-b4f74ceed8f6");

    public override string Description =>
        "Adds \"Untrack show\" to the episode/show menu in the web client and Jellyfin mobile apps: marks the whole show unplayed for you, removing it from Continue Watching and Next Up.";
}
