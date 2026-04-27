import React, { useState, useEffect } from 'react';
import { Server, Plus, Trash2, ExternalLink, Check, X, Key } from 'lucide-react';
import { fetchMCPServers, addMCPServer, removeMCPServer } from '../../lib/api';

interface MCPServer {
  name: string;
  command: string;
  args: string[];
  env?: Record<string, string>;
}

export function MCPPanel() {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newServer, setNewServer] = useState({
    name: '',
    command: '',
    args: '',
    env: '',
  });
  const [adding, setAdding] = useState(false);

  const loadServers = async () => {
    try {
      setLoading(true);
      const data = await fetchMCPServers();
      setServers(data.servers || []);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to load MCP servers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadServers();
  }, []);

  const handleAddServer = async () => {
    if (!newServer.name || !newServer.command) {
      setError('Name and command are required');
      return;
    }

    try {
      setAdding(true);
      const server: MCPServer = {
        name: newServer.name,
        command: newServer.command,
        args: newServer.args ? newServer.args.split(' ').filter(arg => arg.trim()) : [],
      };

      if (newServer.env) {
        try {
          server.env = JSON.parse(newServer.env);
        } catch {
          setError('Invalid JSON in environment variables');
          return;
        }
      }

      const result = await addMCPServer(server);
      if (result.success) {
        setServers(result.servers);
        setNewServer({ name: '', command: '', args: '', env: '' });
        setShowAddForm(false);
        setError(null);
      } else {
        setError(result.error || 'Failed to add server');
      }
    } catch (e: any) {
      setError(e.message || 'Failed to add server');
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveServer = async (serverName: string) => {
    try {
      const result = await removeMCPServer(serverName);
      if (result.success) {
        setServers(result.servers);
        setError(null);
      } else {
        setError(result.error || 'Failed to remove server');
      }
    } catch (e: any) {
      setError(e.message || 'Failed to remove server');
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center space-x-2 mb-4">
          <Server className="w-5 h-5 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900">MCP Servers</h3>
        </div>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Server className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-medium text-gray-900">MCP Servers</h3>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={14} />
          Add Server
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {showAddForm && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Add MCP Server</h4>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={newServer.name}
                onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., github"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Command</label>
              <input
                type="text"
                value={newServer.command}
                onChange={(e) => setNewServer({ ...newServer, command: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., npx"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Arguments (space-separated)</label>
              <input
                type="text"
                value={newServer.args}
                onChange={(e) => setNewServer({ ...newServer, args: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., @modelcontextprotocol/server-github"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Environment Variables (JSON, optional)
              </label>
              <textarea
                value={newServer.env}
                onChange={(e) => setNewServer({ ...newServer, env: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                rows={3}
                placeholder='{"GITHUB_PERSONAL_ACCESS_TOKEN": "your_token"}'
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAddServer}
                disabled={adding}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
              >
                {adding ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Check size={14} />
                    Add Server
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setNewServer({ name: '', command: '', args: '', env: '' });
                }}
                className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                <X size={14} />
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {servers.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Server className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">No MCP servers configured</p>
            <p className="text-xs mt-1">Add a server to extend Jarvis with external tools</p>
          </div>
        ) : (
          servers.map((server) => (
            <div
              key={server.name}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-sm font-medium text-gray-900 truncate">{server.name}</h4>
                  {server.env && Object.keys(server.env).length > 0 && (
                    <Key size={12} className="text-yellow-600" />
                  )}
                </div>
                <div className="text-xs text-gray-600 font-mono truncate">
                  {server.command} {server.args.join(' ')}
                </div>
              </div>
              <div className="flex items-center gap-2 ml-4">
                <button
                  onClick={() => window.open('https://modelcontextprotocol.io', '_blank')}
                  className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
                  title="Learn about MCP"
                >
                  <ExternalLink size={14} />
                </button>
                <button
                  onClick={() => handleRemoveServer(server.name)}
                  className="p-1.5 text-red-400 hover:text-red-600 transition-colors"
                  title="Remove server"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="mt-6 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          MCP (Model Context Protocol) servers provide external tools and data sources to Jarvis.
          <a
            href="https://modelcontextprotocol.io"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-700 ml-1"
          >
            Learn more →
          </a>
        </p>
      </div>
    </div>
  );
}