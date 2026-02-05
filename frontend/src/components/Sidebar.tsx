'use client';

import { Wand2, Loader2, Sparkles } from 'lucide-react';
import { type RoomObject, getObjectIcon } from '@/lib/types';

interface SidebarProps {
    objects: RoomObject[];
    selectedObjectId: string | null;
    isAnalyzing: boolean;
    isGeneratingLayouts: boolean;
    hasImage: boolean;
    onAnalyze: () => void;
    onGenerateLayouts: () => void;
    onObjectSelect: (id: string) => void;
}

// Color mapping for objects
const getObjectStyle = (label: string): { bg: string; text: string } => {
    const labelLower = label.toLowerCase();

    if (labelLower.includes('bed')) {
        return { bg: 'bg-[#fce4d9]', text: 'text-[#8b6355]' };
    }
    if (labelLower.includes('sofa') || labelLower.includes('couch')) {
        return { bg: 'bg-[#ffe4e4]', text: 'text-[#8b5555]' };
    }
    if (labelLower.includes('chair') || labelLower.includes('desk')) {
        return { bg: 'bg-[#e4f4e4]', text: 'text-[#558b55]' };
    }
    if (labelLower.includes('table') || labelLower.includes('dining')) {
        return { bg: 'bg-[#e4e4f4]', text: 'text-[#55558b]' };
    }
    if (labelLower.includes('door') || labelLower.includes('window')) {
        return { bg: 'bg-[#f0f0f0]', text: 'text-[#666666]' };
    }

    return { bg: 'bg-[#f5f5f5]', text: 'text-[#666666]' };
};

// Format label for display
const formatLabel = (label: string): string => {
    return label
        .split('_')[0]
        .split('-')[0]
        .replace(/([A-Z])/g, ' $1')
        .replace(/^./, str => str.toUpperCase())
        .trim();
};

export function Sidebar({
    objects,
    selectedObjectId,
    isAnalyzing,
    isGeneratingLayouts,
    hasImage,
    onAnalyze,
    onGenerateLayouts,
    onObjectSelect,
}: SidebarProps) {
    const hasObjects = objects.length > 0;

    // Group objects by type for display
    const movableObjects = objects.filter(o => o.type === 'movable');
    const structuralObjects = objects.filter(o => o.type === 'structural');

    return (
        <div className="h-full flex flex-col gap-6 p-6">
            {/* Style Header */}
            <div className="text-center">
                <h2 className="title-script text-2xl mb-1">Light & Airy</h2>
                <p className="text-sm text-gray-400">Pocket Planner</p>
            </div>

            {/* Analyze Button */}
            {!hasObjects && (
                <button
                    onClick={onAnalyze}
                    disabled={!hasImage || isAnalyzing}
                    className="btn-analyze flex items-center justify-center gap-2 w-full"
                >
                    {isAnalyzing ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Analyzing...
                        </>
                    ) : (
                        <>
                            <Wand2 className="w-4 h-4" />
                            Analyze Room
                        </>
                    )}
                </button>
            )}

            {/* Objects List */}
            {hasObjects && (
                <div className="flex flex-col gap-6 overflow-y-auto pr-1 flex-1 min-h-0">
                    {/* Movable Objects */}
                    {movableObjects.length > 0 && (
                        <div>
                            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                                Movable Furniture
                            </h3>
                            <div className="grid grid-cols-2 gap-3">
                                {movableObjects.map((obj) => {
                                    const style = getObjectStyle(obj.label);
                                    const isSelected = obj.id === selectedObjectId;
                                    const icon = getObjectIcon(obj.label);

                                    return (
                                        <button
                                            key={obj.id}
                                            onClick={() => onObjectSelect(obj.id)}
                                            className={`
                                                relative flex flex-col items-center justify-center p-3 rounded-xl
                                                transition-all duration-200 aspect-[4/3]
                                                ${style.bg} ${style.text}
                                                ${isSelected
                                                    ? 'ring-2 ring-offset-1 ring-gray-400 shadow-md scale-[1.02]'
                                                    : 'hover:shadow-sm hover:scale-[1.02]'
                                                }
                                            `}
                                        >
                                            <span className="text-2xl mb-1 filter drop-shadow-sm">{icon}</span>
                                            <span className="text-xs font-semibold text-center leading-tight px-1">
                                                {formatLabel(obj.label)}
                                            </span>
                                            {obj.is_locked && (
                                                <span className="absolute top-1.5 right-1.5 text-[0.6rem]">🔒</span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* Structural Objects */}
                    {structuralObjects.length > 0 && (
                        <div>
                            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
                                Structural
                            </h3>
                            <div className="grid grid-cols-2 gap-3">
                                {structuralObjects.map((obj) => {
                                    const icon = getObjectIcon(obj.label);
                                    return (
                                        <div
                                            key={obj.id}
                                            className="
                                                flex flex-col items-center justify-center p-3 rounded-xl
                                                bg-gray-50 border border-gray-100 text-gray-500
                                                aspect-[4/3]
                                            "
                                        >
                                            <span className="text-xl mb-1 opacity-70">{icon}</span>
                                            <span className="text-xs font-medium text-center leading-tight w-full truncate px-1">
                                                {formatLabel(obj.label)}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Generate Layouts Button - Primary Action after analysis */}
            {hasObjects && (
                <button
                    onClick={onGenerateLayouts}
                    disabled={isGeneratingLayouts || movableObjects.length === 0}
                    className="btn-primary flex items-center justify-center gap-2 w-full mt-auto py-3 px-4 bg-gradient-to-r from-[#6b7aa1] to-[#8b9ac1] text-white rounded-xl font-medium hover:from-[#5a6890] hover:to-[#7a89b0] transition-all shadow-lg disabled:opacity-50"
                >
                    {isGeneratingLayouts ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Generating...
                        </>
                    ) : (
                        <>
                            <Sparkles className="w-4 h-4" />
                            Generate Layouts
                        </>
                    )}
                </button>
            )}

            {/* Re-analyze button when objects exist */}
            {hasObjects && (
                <button
                    onClick={onAnalyze}
                    disabled={!hasImage || isAnalyzing}
                    className="btn-secondary flex items-center justify-center gap-2 w-full text-sm text-gray-500 hover:text-gray-700"
                >
                    {isAnalyzing ? (
                        <>
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Analyzing...
                        </>
                    ) : (
                        <>
                            <Wand2 className="w-3 h-3" />
                            Re-Analyze
                        </>
                    )}
                </button>
            )}
        </div>
    );
}
