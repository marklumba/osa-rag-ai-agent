import React, { useState } from 'react';
import { Check, Download } from 'lucide-react';
import * as XLSX from 'xlsx';

/**
 * ENHANCED LIGHTWEIGHT MARKDOWN RENDERER
 * WITH COPY AND EXPORT FEATURES
 * 
 * Features: Tables, Headings, Bullets, Code, Blockquotes, Bold text
 * NEW: Copy button and Excel export for tables
 * 
 * Installation required:
 * npm install xlsx lucide-react
 * 
 * Usage:
 * import LightweightRenderer from './components/enhanced-lightweight-renderer';
 * <LightweightRenderer content={message.content} />
 */

const LightweightRenderer = ({ content }) => {
  const [copiedIndex, setCopiedIndex] = useState(null);

  const parseContent = (text) => {
    const sections = [];
    const lines = text.split('\n');
    let i = 0;
    
    while (i < lines.length) {
      const line = lines[i];
      
      // Check if this is a table
      if (line.trim().startsWith('|')) {
        const tableLines = [];
        while (i < lines.length && lines[i].trim().startsWith('|')) {
          tableLines.push(lines[i]);
          i++;
        }
        
        if (tableLines.length >= 2) {
          sections.push({ type: 'table', content: tableLines });
        }
        continue;
      }
      
      // Check for bullet list (starts with *)
      if (line.trim().startsWith('* ')) {
        const bulletItems = [];
        while (i < lines.length && lines[i].trim().startsWith('* ')) {
          bulletItems.push(lines[i].trim().replace(/^\*\s+/, ''));
          i++;
        }
        sections.push({ type: 'bulletList', content: bulletItems });
        continue;
      }
      
      // Check for headings
      if (line.startsWith('## ')) {
        sections.push({ 
          type: 'h2', 
          content: line.replace('## ', '') 
        });
      } else if (line.startsWith('### ')) {
        sections.push({ 
          type: 'h3', 
          content: line.replace('### ', '') 
        });
      } else if (line.startsWith('> ')) {
        sections.push({ 
          type: 'blockquote', 
          content: line.replace('> ', '') 
        });
      } else if (line.trim()) {
        sections.push({ 
          type: 'text', 
          content: line 
        });
      }
      
      i++;
    }
    
    return sections;
  };

  const parseTableData = (lines) => {
    if (lines.length < 2) return null;
    
    const headers = lines[0]
      .split('|')
      .filter(h => h.trim())
      .map(h => h.trim());
    
    const rows = lines.slice(2).map(row => 
      row.split('|')
        .filter(c => c.trim())
        .map(c => c.trim())
    );
    
    return { headers, rows };
  };

  const exportTableToExcel = (tableData, index) => {
    const { headers, rows } = tableData;
    
    // Create workbook and worksheet
    const wb = XLSX.utils.book_new();
    const wsData = [headers, ...rows];
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    
    // Auto-size columns
    const colWidths = headers.map((_, colIndex) => {
      const maxLength = Math.max(
        headers[colIndex].length,
        ...rows.map(row => (row[colIndex] || '').toString().length)
      );
      return { wch: Math.min(maxLength + 2, 50) };
    });
    ws['!cols'] = colWidths;
    
    XLSX.utils.book_append_sheet(wb, ws, 'Table Data');
    
    // Generate filename with timestamp
    const timestamp = new Date().toISOString().split('T')[0];
    const filename = `table_export_${timestamp}_${index}.xlsx`;
    
    XLSX.writeFile(wb, filename);
    
    // Show success feedback
    setCopiedIndex(`export-${index}`);
    setTimeout(() => setCopiedIndex(null), 2000);
  };
  
  const renderTable = (lines, tableIndex) => {
    if (lines.length < 2) return null;
    
    const tableData = parseTableData(lines);
    const { headers, rows } = tableData;
    
    return (
      <div className="my-4">
        {/* Export Button */}
        <div className="flex justify-end mb-2">
          <button
            onClick={() => exportTableToExcel(tableData, tableIndex)}
            className="flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors duration-200 shadow-sm"
            title="Export to Excel"
          >
            {copiedIndex === `export-${tableIndex}` ? (
              <>
                <Check size={30} />
                <span>Exported!</span>
              </>
            ) : (
              <>
                <Download size={30} />
                <span>Export to Excel</span>
              </>
            )}
          </button>
        </div>
        
        {/* Table */}
        <div className="overflow-x-auto rounded-lg shadow-lg border border-gray-200">
          <table className="min-w-full">
            <thead className="bg-gradient-to-r from-purple-600 to-purple-500">
              <tr>
                {headers.map((header, idx) => (
                  <th 
                    key={idx} 
                    className="px-4 py-3 text-left text-xs font-semibold text-white uppercase"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {rows.map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-purple-50 transition-colors">
                  {row.map((cell, cellIdx) => (
                    <td 
                      key={cellIdx} 
                      className="px-4 py-3 text-sm text-gray-800"
                      dangerouslySetInnerHTML={{ __html: formatText(cell) }}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };
  
  const formatText = (text) => {
    return text
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-900">$1</strong>')
      // Inline code with backticks
      .replace(/`([^`]+)`/g, '<code class="bg-purple-100 text-purple-800 px-2 py-1 rounded text-sm font-mono">$1</code>');
  };
  
  const sections = parseContent(content);
  let tableCounter = 0;
  
  return (
    <div className="space-y-3">
      {sections.map((section, idx) => {
        if (section.type === 'table') {
          const currentTableIndex = tableCounter++;
          return <div key={idx}>{renderTable(section.content, currentTableIndex)}</div>;
        }
        
        if (section.type === 'bulletList') {
          return (
            <ul key={idx} className="space-y-2 my-3 ml-2">
              {section.content.map((item, itemIdx) => (
                <li key={itemIdx} className="flex items-start">
                  <span className="text-purple-600 font-bold mr-3 mt-0.5 text-lg select-none">•</span>
                  <span 
                    className="text-gray-700 leading-relaxed flex-1"
                    dangerouslySetInnerHTML={{ __html: formatText(item) }}
                  />
                </li>
              ))}
            </ul>
          );
        }
        
        if (section.type === 'h2') {
          return (
            <h2 key={idx} className="text-2xl font-bold mt-6 mb-3 text-gray-800">
              {section.content}
            </h2>
          );
        }
        
        if (section.type === 'h3') {
          return (
            <h3 key={idx} className="text-xl font-semibold mt-4 mb-2 text-gray-700">
              {section.content}
            </h3>
          );
        }
        
        if (section.type === 'blockquote') {
          return (
            <div 
              key={idx} 
              className="border-l-4 border-purple-500 bg-purple-50 p-4 my-4 rounded-r-lg"
              dangerouslySetInnerHTML={{ __html: formatText(section.content) }}
            />
          );
        }
        
        return (
          <p 
            key={idx} 
            className="text-gray-700 leading-relaxed"
            dangerouslySetInnerHTML={{ __html: formatText(section.content) }}
          />
        );
      })}
    </div>
  );
};

export default LightweightRenderer;