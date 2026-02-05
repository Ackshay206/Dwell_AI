'use client';

import { ArrowLeft, Loader2, Check } from 'lucide-react';
import type { LayoutVariation, RoomDimensions, RoomObject } from '@/lib/types';

interface LayoutSelectorProps {
    variations: LayoutVariation[];
    roomDimensions: RoomDimensions | null;
    isLoading: boolean;
    onSelect: (variation: LayoutVariation) => void;
    onBack: () => void;
}

// Color mapping for furniture types
const getObjectColor = (label: string): string => {
    const labelLower = label.toLowerCase();
    if (labelLower.includes('bed')) return '#e8b4a8';
    if (labelLower.includes('sofa') || labelLower.includes('couch')) return '#f5c4c4';
    if (labelLower.includes('chair')) return '#c4e8c4';
    if (labelLower.includes('desk')) return '#c4d4e8';
    if (labelLower.includes('table')) return '#e8e4c4';
    if (labelLower.includes('door')) return '#a8c8d8';
    if (labelLower.includes('window')) return '#d8e8f0';
    if (labelLower.includes('wardrobe') || labelLower.includes('closet')) return '#d8c8b8';
    return '#d8d8d8';
};

// Mini preview component to show layout
function LayoutPreview({ layout, roomDimensions }: { layout: RoomObject[]; roomDimensions: RoomDimensions | null }) {
    if (layout.length === 0) {
        return (
            <div className="w-full h-full flex items-center justify-center">
                <span className="text-xs text-gray-400">No preview</span>
            </div>
        );
    }

    // Calculate bounds of all objects to determine coordinate system
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    layout.forEach(obj => {
        const [x, y, w, h] = obj.bbox;
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x + w);
        maxY = Math.max(maxY, y + h);
    });

    // Add padding
    const padding = Math.max((maxX - minX), (maxY - minY)) * 0.1;
    const viewX = minX - padding;
    const viewY = minY - padding;
    const viewW = (maxX - minX) + (padding * 2);
    const viewH = (maxY - minY) + (padding * 2);

    return (
        <svg
            viewBox={`${viewX} ${viewY} ${viewW} ${viewH}`}
            className="w-full h-full bg-[#faf9f7]"
            preserveAspectRatio="xMidYMid meet"
        >
            {/* Furniture items */}
            {layout.map((obj, i) => {
                const [x, y, w, h] = obj.bbox;
                const color = getObjectColor(obj.label);
                const isStructural = obj.type === 'structural';

                return (
                    <g key={obj.id || i}>
                        {/* Object rectangle */}
                        <rect
                            x={x}
                            y={y}
                            width={w}
                            height={h}
                            fill={color}
                            stroke={isStructural ? '#666' : '#888'}
                            strokeWidth={Math.max(1, viewW * 0.005)} // Adaptive stroke width
                            strokeDasharray={isStructural ? `${viewW * 0.01},${viewW * 0.005}` : 'none'}
                            rx={viewW * 0.01} // Adaptive radius
                            fillOpacity={0.8}
                        />
                        {/* Label - only show if object is large enough relative to view */}
                        {w > viewW * 0.05 && h > viewH * 0.05 && (
                            <text
                                x={x + w / 2}
                                y={y + h / 2}
                                textAnchor="middle"
                                dominantBaseline="middle"
                                fontSize={viewW * 0.04} // Adaptive font size
                                fill="#555"
                                className="pointer-events-none font-medium opacity-80"
                                style={{ textShadow: '0px 0px 2px rgba(255,255,255,0.5)' }}
                            >
                                {obj.label.split('_')[0].charAt(0).toUpperCase()}
                            </text>
                        )}
                    </g>
                );
            })}
        </svg>
    );
}

export function LayoutSelector({
    variations,
    roomDimensions,
    isLoading,
    onSelect,
    onBack,
}: LayoutSelectorProps) {
    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
                <Loader2 className="w-12 h-12 animate-spin text-[#6b7aa1]" />
                <p className="text-gray-500 text-lg">Generating layout variations...</p>
                <p className="text-gray-400 text-sm">Our AI is creating 3 unique designs for you</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <button
                    onClick={onBack}
                    className="p-2 rounded-full hover:bg-gray-100 transition-colors"
                >
                    <ArrowLeft className="w-5 h-5 text-gray-600" />
                </button>
                <div>
                    <h2 className="text-xl font-semibold text-gray-800">Choose Your Layout</h2>
                    <p className="text-sm text-gray-500">Select one of the AI-generated options</p>
                </div>
            </div>

            {/* Layout Cards */}
            <div className="grid gap-6 md:grid-cols-3">
                {variations.map((variation, index) => (
                    <div
                        key={index}
                        className="card p-4 hover:shadow-lg transition-all cursor-pointer group border-2 border-transparent hover:border-[#6b7aa1]/30"
                        onClick={() => onSelect(variation)}
                    >
                        {/* Layout Preview */}
                        <div className="aspect-square bg-gradient-to-br from-[#faf9f7] to-[#f0eeea] rounded-xl mb-4 relative overflow-hidden p-2 border border-gray-100">
                            {/* Score Badge */}
                            {variation.score != null && (
                                <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-1 rounded-full text-xs font-medium text-[#6b7aa1] z-10 shadow-sm">
                                    {Math.round(variation.score)}%
                                </div>
                            )}

                            {/* Thumbnail image if available, otherwise render preview */}
                            {variation.thumbnail_base64 ? (
                                <img
                                    src={`data:image/png;base64,${variation.thumbnail_base64}`}
                                    alt={variation.name}
                                    className="w-full h-full object-contain rounded-lg"
                                />
                            ) : (
                                <LayoutPreview
                                    layout={variation.layout}
                                    roomDimensions={roomDimensions}
                                />
                            )}

                            {/* Hover Overlay */}
                            <div className="absolute inset-0 bg-[#6b7aa1]/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-xl">
                                <div className="bg-white rounded-full p-3 shadow-lg">
                                    <Check className="w-6 h-6 text-[#6b7aa1]" />
                                </div>
                            </div>
                        </div>

                        {/* Layout Info */}
                        <h3 className="font-semibold text-gray-800 mb-1">{variation.name}</h3>
                        <p className="text-sm text-gray-500 line-clamp-3">{variation.description}</p>

                        {/* Object count */}
                        <div className="mt-2 flex gap-2 flex-wrap">
                            {variation.layout.filter(o => o.type === 'movable').length > 0 && (
                                <span className="text-xs px-2 py-1 bg-[#e8f4e8] text-[#558b55] rounded-full">
                                    {variation.layout.filter(o => o.type === 'movable').length} movable
                                </span>
                            )}
                            {variation.layout.filter(o => o.type === 'structural').length > 0 && (
                                <span className="text-xs px-2 py-1 bg-[#f0f0f0] text-[#666] rounded-full">
                                    {variation.layout.filter(o => o.type === 'structural').length} fixed
                                </span>
                            )}
                        </div>

                        {/* Select Button */}
                        <button
                            className="w-full mt-4 py-2 px-4 bg-[#6b7aa1] text-white rounded-xl font-medium hover:bg-[#5a6890] transition-colors"
                            onClick={(e) => {
                                e.stopPropagation();
                                onSelect(variation);
                            }}
                        >
                            Select This Layout
                        </button>
                    </div>
                ))}
            </div>

            {/* Dynamic Legend */}
            <div className="flex flex-wrap justify-center gap-6 text-xs text-gray-500 mt-8 pt-6 border-t border-gray-100">
                {(() => {
                    const uniqueLabels = new Set<string>();
                    variations.forEach(v => v.layout.forEach(o => uniqueLabels.add(o.label)));

                    return Array.from(uniqueLabels).map(label => {
                        const color = getObjectColor(label);
                        const cleanLabel = label.split('_')[0].charAt(0).toUpperCase() + label.split('_')[0].slice(1);
                        return (
                            <div key={label} className="flex items-center gap-1.5 bg-white px-2 py-1 rounded-md shadow-sm border border-gray-100">
                                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                                <span>{cleanLabel}</span>
                            </div>
                        );
                    });
                })()}
            </div>

            {/* Room Info */}
            {roomDimensions && (
                <div className="text-center text-sm text-gray-400">
                    Room: {roomDimensions.width_estimate.toFixed(1)} × {roomDimensions.height_estimate.toFixed(1)} ft
                </div>
            )}
        </div>
    );
}
