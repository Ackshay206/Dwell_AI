'use client';

import { useEffect, useRef, useState } from 'react';
import { Stage, Layer, Rect, Image as KonvaImage, Group } from 'react-konva';
import type { RoomObject } from '@/lib/types';

interface CanvasOverlayProps {
    imageUrl: string;
    objects: RoomObject[];
    selectedObjectId: string | null;
    onObjectSelect: (id: string) => void;
}

// Simplified color scheme - matching reference design
const COLORS = {
    primary: { stroke: '#f4a582', fill: 'rgba(244, 165, 130, 0.15)' },   // Coral/salmon
    secondary: { stroke: '#80cdc1', fill: 'rgba(128, 205, 193, 0.15)' }, // Cyan/teal
    selected: { stroke: '#f4a582', fill: 'rgba(244, 165, 130, 0.25)' },  // Highlighted coral
};

// Determine color based on object type
const getObjectColor = (obj: RoomObject, isSelected: boolean) => {
    if (isSelected) return COLORS.selected;

    const label = obj.label.toLowerCase();
    // Primary items (bed, sofa) get coral color
    if (label.includes('bed') || label.includes('sofa') || label.includes('couch')) {
        return COLORS.primary;
    }
    // Others get cyan color
    return COLORS.secondary;
};

export function CanvasOverlay({
    imageUrl,
    objects,
    selectedObjectId,
    onObjectSelect,
}: CanvasOverlayProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const [image, setImage] = useState<HTMLImageElement | null>(null);
    const [scale, setScale] = useState(1);
    const [hoveredId, setHoveredId] = useState<string | null>(null);

    // Load image
    useEffect(() => {
        const img = new window.Image();
        img.src = imageUrl;
        img.onload = () => {
            setImage(img);

            // Calculate scale to fit container
            if (containerRef.current) {
                const containerWidth = containerRef.current.clientWidth;
                const containerHeight = Math.min(550, window.innerHeight * 0.65);
                const scaleX = containerWidth / img.width;
                const scaleY = containerHeight / img.height;
                const newScale = Math.min(scaleX, scaleY, 1);

                setScale(newScale);
                setDimensions({
                    width: img.width * newScale,
                    height: img.height * newScale,
                });
            }
        };
    }, [imageUrl]);

    // Handle resize
    useEffect(() => {
        const handleResize = () => {
            if (containerRef.current && image) {
                const containerWidth = containerRef.current.clientWidth;
                const containerHeight = Math.min(550, window.innerHeight * 0.65);
                const scaleX = containerWidth / image.width;
                const scaleY = containerHeight / image.height;
                const newScale = Math.min(scaleX, scaleY, 1);

                setScale(newScale);
                setDimensions({
                    width: image.width * newScale,
                    height: image.height * newScale,
                });
            }
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [image]);

    // Get stroke width based on state
    const getStrokeWidth = (objId: string) => {
        const isHovered = hoveredId === objId;
        const isSelected = objId === selectedObjectId;

        if (isSelected) return 3;
        if (isHovered) return 2.5;
        return 2;
    };

    if (!image) {
        return (
            <div ref={containerRef} className="w-full h-[400px] flex items-center justify-center bg-gray-50 rounded-2xl">
                <div className="text-gray-400">Loading image...</div>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="w-full flex justify-center">
            <div className="floor-plan-container inline-block">
                <Stage
                    width={dimensions.width}
                    height={dimensions.height}
                    className="rounded-2xl overflow-hidden"
                >
                    <Layer>
                        {/* Background Image */}
                        <KonvaImage
                            image={image}
                            width={dimensions.width}
                            height={dimensions.height}
                        />

                        {/* Object Bounding Boxes */}
                        {objects.map((obj) => {
                            const isSelected = obj.id === selectedObjectId;
                            const colors = getObjectColor(obj, isSelected);
                            const strokeWidth = getStrokeWidth(obj.id);
                            const [x, y, width, height] = obj.bbox;

                            return (
                                <Group key={obj.id}>
                                    <Rect
                                        x={x * scale}
                                        y={y * scale}
                                        width={width * scale}
                                        height={height * scale}
                                        stroke={colors.stroke}
                                        fill={colors.fill}
                                        strokeWidth={strokeWidth}
                                        cornerRadius={4}
                                        onClick={() => onObjectSelect(obj.id)}
                                        onMouseEnter={() => setHoveredId(obj.id)}
                                        onMouseLeave={() => setHoveredId(null)}
                                    // CSS cursor via Konva doesn't work directly, handled by style
                                    />
                                </Group>
                            );
                        })}
                    </Layer>
                </Stage>
            </div>
        </div>
    );
}
