using System.Text.Json.Serialization;
using MediaBrowser.Common.Net;

namespace Jellyfin.Plugin.UntrackShow;

/// <summary>Called by File Transformation whenever the web client's index.html is served.</summary>
public static class Transformations
{
    private const string Marker = "plugin=\"UntrackShow\"";

    public static string IndexTransformation(PatchRequestPayload payload)
    {
        string contents = payload.Contents ?? string.Empty;
        if (contents.Contains(Marker, StringComparison.Ordinal))
        {
            return contents;
        }

        string baseUrl = Plugin.Instance?.ServerConfigurationManager.GetNetworkConfiguration().BaseUrl?.Trim().Trim('/') ?? string.Empty;
        string basePath = baseUrl.Length > 0 ? "/" + baseUrl : string.Empty;
        string version = typeof(Transformations).Assembly.GetName().Version?.ToString() ?? "1";
        string script = $"<script {Marker} defer=\"defer\" src=\"{basePath}/UntrackShow/script?v={version}\"></script>";

        int bodyClosing = contents.LastIndexOf("</body>", StringComparison.OrdinalIgnoreCase);
        return bodyClosing < 0 ? contents : contents.Insert(bodyClosing, script);
    }
}

public class PatchRequestPayload
{
    [JsonPropertyName("contents")]
    public string? Contents { get; set; }
}
