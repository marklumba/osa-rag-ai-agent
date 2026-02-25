import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Markdown Renderer with Dynamic Bullets
 *
 * Usage:
 *   <MarkdownRenderer content={message.content} bullet="•" />
 */

const MarkdownRenderer = ({ content, bullet = "•" }) => {
  return (
    <div className="prose max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Tables
          table: ({ children }) => (
            <div className="overflow-x-auto my-4 rounded-lg shadow-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-300">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-gradient-to-r from-purple-600 to-purple-500">
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 text-left text-xs font-semibold text-white uppercase tracking-wider">
              {children}
            </th>
          ),
          tbody: ({ children }) => (
            <tbody className="bg-white divide-y divide-gray-200">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-purple-50 transition-colors duration-150">
              {children}
            </tr>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 text-sm text-gray-800">
              {children}
            </td>
          ),

          // Headings
          h2: ({ children }) => (
            <h2 className="text-2xl font-bold mt-6 mb-3 text-gray-800">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-xl font-semibold mt-4 mb-2 text-gray-700">
              {children}
            </h3>
          ),

          // Code
          code: ({ inline, children }) => {
            if (inline) {
              return (
                <code className="bg-purple-100 text-purple-800 px-2 py-1 rounded text-sm font-mono">
                  {children}
                </code>
              );
            }
            return (
              <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-4">
                <code className="text-sm">{children}</code>
              </pre>
            );
          },

          // Blockquotes
          blockquote: ({ children }) => (
            <div className="border-l-4 border-purple-500 bg-purple-50 p-4 my-4 rounded-r-lg">
              {children}
            </div>
          ),

          // Bold
          strong: ({ children }) => (
            <strong className="font-bold text-gray-900">
              {children}
            </strong>
          ),

          // Lists
          ul: ({ children }) => (
            <ul className="mb-4 ml-4 space-y-2">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside mb-4 ml-4 space-y-2">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="flex items-start">
              <span className="mr-2 text-purple-600">{bullet}</span>
              <span>{children}</span>
            </li>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;