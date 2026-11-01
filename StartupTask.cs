using System.Reflection;
using System.Runtime.Loader;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.UntrackShow;

/// <summary>
/// On server start, asks the File Transformation plugin to add our script to the web client's index.html.
/// File Transformation lives in its own load context, so it is reached through reflection.
/// </summary>
public class StartupTask : IScheduledTask
{
    private const string TransformationId = "438721fa-a70e-47c1-8434-84a429f1c54a";

    private readonly ILogger<StartupTask> _logger;

    public StartupTask(ILogger<StartupTask> logger)
    {
        _logger = logger;
    }

    public string Name => "Untrack Show Startup";

    public string Key => "Jellyfin.Plugin.UntrackShow.Startup";

    public string Description => "Registers the Untrack Show menu script with File Transformation.";

    public string Category => "Startup Services";

    public Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
    {
        Assembly? fileTransformation = AssemblyLoadContext.All
            .SelectMany(context => context.Assemblies)
            .FirstOrDefault(assembly => assembly.FullName?.Contains(".FileTransformation", StringComparison.OrdinalIgnoreCase) ?? false);

        MethodInfo? register = fileTransformation?
            .GetType("Jellyfin.Plugin.FileTransformation.PluginInterface")?
            .GetMethod("RegisterTransformation");

        if (register is null)
        {
            _logger.LogWarning("Untrack Show needs the File Transformation plugin, which was not found.");
            return Task.CompletedTask;
        }

        JObject payload = new JObject
        {
            { "id", TransformationId },
            { "fileNamePattern", "index.html" },
            { "callbackAssembly", typeof(StartupTask).Assembly.FullName },
            { "callbackClass", typeof(Transformations).FullName },
            { "callbackMethod", nameof(Transformations.IndexTransformation) }
        };

        object? result = register.Invoke(null, new object?[] { payload });
        if (result is false)
        {
            _logger.LogWarning("File Transformation rejected the Untrack Show registration.");
        }
        else
        {
            _logger.LogInformation("Untrack Show registered its menu script with File Transformation.");
        }

        return Task.CompletedTask;
    }

    public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
    {
        yield return new TaskTriggerInfo { Type = TaskTriggerInfoType.StartupTrigger };
    }
}
