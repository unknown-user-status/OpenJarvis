import React, { useState, useEffect } from 'react';
import { Bot, ChevronDown, Check } from 'lucide-react';
import { fetchAgents } from '../../lib/api';
import { useAppStore } from '../../lib/store';

interface Agent {
  id: string;
  name: string;
  description?: string;
  class: string;
}

export function AgentSelector() {
  const selectedAgent = useAppStore((s) => s.selectedAgent) || 'simple';
  const setSelectedAgent = useAppStore((s) => s.setSelectedAgent);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchAgents();
        setAgents(data.agents || []);
      } catch (e) {
        console.error('Failed to load agents:', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const currentAgent = agents.find(a => a.id === selectedAgent) || { id: selectedAgent, name: selectedAgent, class: '' };

  if (loading) {
    return (
      <div className="px-3 mb-2">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm animate-pulse" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
          <Bot size={14} />
          <div className="flex-1 h-4 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 mb-2">
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 w-full px-3 py-1.5 rounded-lg text-sm transition-colors hover:bg-opacity-80"
          style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <Bot size={14} style={{ color: 'var(--color-accent-purple)' }} />
          <div className="flex-1 min-w-0 text-left">
            <span className="truncate block">{currentAgent.name}</span>
          </div>
          <ChevronDown 
            size={14} 
            style={{ 
              color: 'var(--color-text-tertiary)',
              transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s'
            }} 
          />
        </button>

        {isOpen && (
          <>
            {/* Backdrop */}
            <div 
              className="fixed inset-0 z-10" 
              onClick={() => setIsOpen(false)}
            />
            
            {/* Dropdown */}
            <div 
              className="absolute top-full left-0 right-0 mt-1 rounded-lg shadow-lg border z-20 max-h-60 overflow-y-auto"
              style={{ 
                background: 'var(--color-bg-primary)', 
                borderColor: 'var(--color-border)',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
              }}
            >
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => {
                    setSelectedAgent(agent.id);
                    setIsOpen(false);
                  }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-left transition-colors hover:bg-opacity-80 first:rounded-t-lg last:rounded-b-lg"
                  style={{ 
                    color: 'var(--color-text)',
                    background: agent.id === selectedAgent ? 'var(--color-bg-secondary)' : 'transparent'
                  }}
                >
                  <Bot size={14} style={{ color: 'var(--color-accent-purple)' }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{agent.name}</span>
                      {agent.id === selectedAgent && (
                        <Check size={12} style={{ color: 'var(--color-accent)' }} />
                      )}
                    </div>
                    {agent.description && (
                      <span className="text-xs truncate block" style={{ color: 'var(--color-text-tertiary)' }}>
                        {agent.description}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}