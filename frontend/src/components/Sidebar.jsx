import React from 'react';
import { LayoutDashboard, ShoppingCart, Settings, History, BarChart2 } from 'lucide-react';

const Sidebar = () => {
  const menuItems = [
    { icon: <LayoutDashboard size={20} />, label: 'Dashboard', active: true },
    { icon: <BarChart2 size={20} />, label: 'My Strategies', active: false },
    { icon: <History size={20} />, label: 'Backtest History', active: false },
    { icon: <ShoppingCart size={20} />, label: 'Marketplace', active: false },
    { icon: <Settings size={20} />, label: 'Settings', active: false },
  ];

  return (
    <aside className="w-64 border-r border-gray-800 bg-gray-900 flex flex-col">
      <div className="p-6">
        <div className="flex items-center gap-3 text-blue-500 mb-8">
          <BarChart2 size={32} />
          <span className="text-xl font-bold text-white italic">SB India</span>
        </div>
        
        <nav className="space-y-1">
          {menuItems.map((item, index) => (
            <button
              key={index}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                item.active 
                  ? 'bg-blue-600 text-white' 
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
      </div>
      
      <div className="mt-auto p-6 border-t border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center font-bold">
            V
          </div>
          <div>
            <p className="text-sm font-medium">Vikram</p>
            <p className="text-xs text-gray-500">Lead Engineer</p>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
