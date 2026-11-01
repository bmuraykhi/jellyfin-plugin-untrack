using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace Jellyfin.Plugin.UntrackShow;

/// <summary>Serves the web client script. It must load before login, so it is anonymous; it contains no data.</summary>
[ApiController]
[Route("UntrackShow")]
public class UntrackShowController : ControllerBase
{
    [HttpGet("script")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [Produces("application/javascript")]
    public ActionResult GetScript()
    {
        Stream? script = typeof(UntrackShowController).Assembly.GetManifestResourceStream("untrack.js");
        return script is null ? NotFound() : File(script, "application/javascript");
    }
}
