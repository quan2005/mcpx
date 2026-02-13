import { useEffect, useState } from "react";
import type { Resource } from "../api/client";
import { api } from "../api/client";
import { useDebounce } from "../hooks/useDebounce";
import { useToast } from "../contexts/ToastContext";

export default function Resources() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [filter, setFilter] = useState("");
  const [serverFilter, setServerFilter] = useState("");
  const [servers, setServers] = useState<string[]>([]);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(
    null,
  );
  const [resourceContent, setResourceContent] = useState<unknown[] | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const { showToast } = useToast();

  // Debounce filter for search optimization
  const debouncedFilter = useDebounce(filter, 300);

  const loadResources = async () => {
    const data = await api.listResources(serverFilter || undefined);
    setResources(data.resources);

    // Extract unique servers
    const uniqueServers = [...new Set(data.resources.map((r) => r.server))];
    setServers(uniqueServers);
  };

  useEffect(() => {
    loadResources();
  }, [serverFilter]);

  const handleRead = async (resource: Resource) => {
    setSelectedResource(resource);
    setLoading(true);
    try {
      const data = await api.readResource(resource.server, resource.uri);
      setResourceContent(data.contents);
    } catch (error) {
      showToast({
        type: "error",
        message: `Failed to read resource: ${error}`,
      });
      setResourceContent([{ error: String(error) }]);
    } finally {
      setLoading(false);
    }
  };

  // Use debounced filter for better performance
  const filteredResources = resources.filter(
    (resource) =>
      resource.name.toLowerCase().includes(debouncedFilter.toLowerCase()) ||
      resource.uri.toLowerCase().includes(debouncedFilter.toLowerCase()),
  );

  // Group by server
  const groupedResources = filteredResources.reduce(
    (acc, resource) => {
      if (!acc[resource.server]) acc[resource.server] = [];
      acc[resource.server].push(resource);
      return acc;
    },
    {} as Record<string, Resource[]>,
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Resources</h2>
        <p className="text-slate-400">Browse and read MCP resources</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="Search resources..."
          className="input max-w-md"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <select
          className="input max-w-xs"
          value={serverFilter}
          onChange={(e) => setServerFilter(e.target.value)}
        >
          <option value="">All Servers</option>
          {servers.map((server) => (
            <option key={server} value={server}>
              {server}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Resources List */}
        <div className="space-y-6">
          {Object.entries(groupedResources).length === 0 ? (
            <div className="card text-center py-12">
              <p className="text-slate-500">No resources found</p>
            </div>
          ) : (
            Object.entries(groupedResources).map(
              ([server, serverResources]) => (
                <div key={server} className="card">
                  <h3 className="text-lg font-semibold text-white mb-4">
                    {server}
                  </h3>
                  <div className="space-y-2">
                    {serverResources.map((resource) => (
                      <button
                        key={`${resource.server}:${resource.uri}`}
                        onClick={() => handleRead(resource)}
                        className={`w-full text-left p-3 rounded-lg transition-colors ${
                          selectedResource?.uri === resource.uri
                            ? "bg-blue-900 border border-blue-700"
                            : "bg-slate-900 hover:bg-slate-800"
                        }`}
                      >
                        <div className="font-medium text-white">
                          {resource.name}
                        </div>
                        <div className="text-sm text-slate-400 truncate">
                          {resource.uri}
                        </div>
                        {resource.mime_type && (
                          <div className="text-xs text-slate-500 mt-1">
                            {resource.mime_type}
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ),
            )
          )}
        </div>

        {/* Resource Preview */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Preview</h3>
          {selectedResource ? (
            <div>
              <div className="mb-4">
                <p className="text-sm text-slate-400">Name</p>
                <p className="text-white">{selectedResource.name}</p>
              </div>
              <div className="mb-4">
                <p className="text-sm text-slate-400">URI</p>
                <p className="text-white font-mono text-sm break-all">
                  {selectedResource.uri}
                </p>
              </div>
              {selectedResource.mime_type && (
                <div className="mb-4">
                  <p className="text-sm text-slate-400">MIME Type</p>
                  <p className="text-white">{selectedResource.mime_type}</p>
                </div>
              )}

              <div className="mt-6">
                <p className="text-sm text-slate-400 mb-2">Content</p>
                {loading ? (
                  <div className="text-slate-500">Loading...</div>
                ) : resourceContent ? (
                  <pre className="bg-slate-900 p-4 rounded-lg text-sm text-slate-300 overflow-auto max-h-96">
                    {JSON.stringify(resourceContent, null, 2)}
                  </pre>
                ) : (
                  <div className="text-slate-500">
                    Click a resource to view its content
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-slate-500 text-center py-12">
              Select a resource to preview
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
