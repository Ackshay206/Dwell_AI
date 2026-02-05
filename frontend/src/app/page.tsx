'use client';

import { useState, useCallback, useEffect } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import { ImageUpload } from '@/components/ImageUpload';
import { CanvasOverlay } from '@/components/CanvasOverlay';
import { Sidebar } from '@/components/Sidebar';
import { LayoutSelector } from '@/components/LayoutSelector';
import { PerspectiveView } from '@/components/PerspectiveView';
import { ChatEditor } from '@/components/ChatEditor';
import { useAnalyze } from '@/hooks/useAnalyze';
import { useOptimize } from '@/hooks/useOptimize';
import { usePerspective } from '@/hooks/usePerspective';
import { useChatEdit } from '@/hooks/useChatEdit';
import type { RoomObject, RoomDimensions, LayoutVariation, AppStage } from '@/lib/types';

interface AppState {
  stage: AppStage;
  image: string | null;
  roomDimensions: RoomDimensions | null;
  objects: RoomObject[];
  selectedObjectId: string | null;
  isAnalyzing: boolean;
  layoutVariations: LayoutVariation[];
  selectedVariation: LayoutVariation | null;
  perspectiveImage: string | null;
  currentLayout: RoomObject[];
}

const initialState: AppState = {
  stage: 'analyze',
  image: null,
  roomDimensions: null,
  objects: [],
  selectedObjectId: null,
  isAnalyzing: false,
  layoutVariations: [],
  selectedVariation: null,
  perspectiveImage: null,
  currentLayout: [],
};

export default function PocketPlannerApp() {
  const [state, setState] = useState<AppState>(initialState);

  const { analyze } = useAnalyze();
  const { optimize, isLoading: isOptimizing } = useOptimize();
  const { generate: generatePerspective, isLoading: isGeneratingPerspective } = usePerspective();
  const { sendCommand, isLoading: isChatLoading, messages } = useChatEdit();

  // === Auto-load test image on mount ===
  useEffect(() => {
    const loadTestImage = async () => {
      try {
        const response = await fetch('/test_img.jpg');
        const blob = await response.blob();
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64 = reader.result as string;
          setState(prev => ({
            ...prev,
            image: base64,
          }));
          toast.success('Test image loaded! Click "Analyze Room" to start.');
        };
        reader.readAsDataURL(blob);
      } catch (error) {
        console.log('No test image found, starting fresh.');
      }
    };
    loadTestImage();
  }, []);

  // === Image Upload ===
  const handleImageSelect = useCallback((base64: string) => {
    setState(prev => ({
      ...prev,
      stage: 'analyze',
      image: `data:image/jpeg;base64,${base64}`,
      objects: [],
      selectedObjectId: null,
      layoutVariations: [],
      selectedVariation: null,
      perspectiveImage: null,
    }));
  }, []);

  // === Analyze ===
  const handleAnalyze = useCallback(async () => {
    if (!state.image) return;

    setState(prev => ({ ...prev, isAnalyzing: true }));

    try {
      const base64 = state.image.split(',')[1];
      const response = await analyze(base64);

      setState(prev => ({
        ...prev,
        roomDimensions: response.room_dimensions,
        objects: response.objects,
        isAnalyzing: false,
        stage: 'analyze',
      }));

      toast.success(`Detected ${response.objects.length} objects`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Analysis failed');
      setState(prev => ({ ...prev, isAnalyzing: false }));
    }
  }, [state.image, analyze]);

  // === Generate Layouts ===
  const handleGenerateLayouts = useCallback(async () => {
    if (!state.roomDimensions || state.objects.length === 0) return;

    try {
      const lockedIds = state.objects
        .filter(o => o.is_locked)
        .map(o => o.id);

      const response = await optimize({
        current_layout: state.objects,
        locked_ids: lockedIds,
        room_dimensions: state.roomDimensions,
        image_base64: state.image ? state.image.split(',')[1] : undefined,
      });

      setState(prev => ({
        ...prev,
        layoutVariations: response.variations,
        stage: 'layouts',
      }));

      toast.success(`Generated ${response.variations.length} layout options`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate layouts');
    }
  }, [state.roomDimensions, state.objects, optimize]);

  // === Select Layout ===
  const handleSelectLayout = useCallback(async (variation: LayoutVariation) => {
    setState(prev => ({
      ...prev,
      selectedVariation: variation,
      currentLayout: variation.layout,
      stage: 'perspective',
    }));

    // Generate perspective
    if (state.roomDimensions) {
      try {
        const response = await generatePerspective({
          layout: variation.layout,
          room_dimensions: state.roomDimensions,
          style: 'modern',
        });

        setState(prev => ({
          ...prev,
          perspectiveImage: response.image_base64,
        }));

        toast.success('Perspective view generated!');
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Failed to generate perspective');
      }
    }
  }, [state.roomDimensions, generatePerspective]);

  // === Continue to Chat Editor ===
  const handleContinueToChat = useCallback(() => {
    setState(prev => ({ ...prev, stage: 'chat' }));
  }, []);

  // === Chat Edit ===
  const handleChatCommand = useCallback(async (command: string) => {
    if (!state.roomDimensions) return;

    try {
      const response = await sendCommand({
        command,
        current_layout: state.currentLayout,
        room_dimensions: state.roomDimensions,
        current_image_base64: state.perspectiveImage || undefined,
      });

      // Update layout if changed
      if (response.updated_layout) {
        setState(prev => ({
          ...prev,
          currentLayout: response.updated_layout,
        }));
      }

      // Update image if changed
      if (response.updated_image_base64) {
        setState(prev => ({
          ...prev,
          perspectiveImage: response.updated_image_base64,
        }));
      }
    } catch (error) {
      // Error is handled by the hook
    }
  }, [state.roomDimensions, state.currentLayout, state.perspectiveImage, sendCommand]);

  // === Navigation ===
  const handleBackToAnalyze = useCallback(() => {
    setState(prev => ({ ...prev, stage: 'analyze' }));
  }, []);

  const handleBackToLayouts = useCallback(() => {
    setState(prev => ({ ...prev, stage: 'layouts' }));
  }, []);

  const handleBackToPerspective = useCallback(() => {
    setState(prev => ({ ...prev, stage: 'perspective' }));
  }, []);

  // === Object Selection ===
  const handleObjectSelect = useCallback((id: string) => {
    setState(prev => ({
      ...prev,
      selectedObjectId: prev.selectedObjectId === id ? null : id,
    }));
  }, []);

  // === Render based on stage ===
  const renderContent = () => {
    switch (state.stage) {
      case 'layouts':
        return (
          <LayoutSelector
            variations={state.layoutVariations}
            roomDimensions={state.roomDimensions}
            isLoading={isOptimizing}
            onSelect={handleSelectLayout}
            onBack={handleBackToAnalyze}
          />
        );

      case 'perspective':
        return (
          <PerspectiveView
            imageBase64={state.perspectiveImage}
            isLoading={isGeneratingPerspective}
            layoutName={state.selectedVariation?.name}
            onContinue={handleContinueToChat}
            onBack={handleBackToLayouts}
          />
        );

      case 'chat':
        return (
          <ChatEditor
            imageBase64={state.perspectiveImage}
            layout={state.currentLayout}
            roomDimensions={state.roomDimensions}
            messages={messages}
            isLoading={isChatLoading}
            onSendCommand={handleChatCommand}
            onBack={handleBackToPerspective}
          />
        );

      case 'analyze':
      default:
        return (
          <div className="flex flex-col lg:flex-row gap-6">
            {/* === Floor Plan Viewer === */}
            <div className="flex-1 min-w-0">
              {state.image && state.objects.length > 0 ? (
                <CanvasOverlay
                  imageUrl={state.image}
                  objects={state.objects}
                  selectedObjectId={state.selectedObjectId}
                  onObjectSelect={handleObjectSelect}
                />
              ) : state.image ? (
                <div className="floor-plan-container p-4">
                  <img
                    src={state.image}
                    alt="Floor plan"
                    className="w-full h-auto rounded-xl"
                  />
                  <div className="text-center mt-4 text-gray-500 text-sm">
                    Click &quot;Analyze Room&quot; to detect objects
                  </div>
                </div>
              ) : (
                <ImageUpload
                  onImageSelect={handleImageSelect}
                  currentImage={state.image}
                  disabled={state.isAnalyzing}
                />
              )}

              {/* Room dimensions */}
              {state.roomDimensions && (
                <div className="text-center text-sm text-gray-400 mt-4">
                  Room: {state.roomDimensions.width_estimate.toFixed(1)} × {state.roomDimensions.height_estimate.toFixed(1)} ft
                </div>
              )}
            </div>

            {/* === Sidebar === */}
            <div className="w-full lg:w-72 shrink-0">
              <Sidebar
                objects={state.objects}
                selectedObjectId={state.selectedObjectId}
                isAnalyzing={state.isAnalyzing}
                isGeneratingLayouts={isOptimizing}
                hasImage={!!state.image}
                onAnalyze={handleAnalyze}
                onGenerateLayouts={handleGenerateLayouts}
                onObjectSelect={handleObjectSelect}
              />
            </div>
          </div>
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f3f0]">
      <Toaster
        position="top-right"
        toastOptions={{
          className: '!bg-white !text-gray-800 !shadow-lg',
          style: {
            borderRadius: '12px',
          },
        }}
      />

      {/* === Header === */}
      <header className="py-8 text-center">
        <h1 className="title-script text-4xl md:text-5xl text-[#6b7aa1]">
          Pocket Planner
        </h1>
        {/* Stage indicator */}
        <div className="flex justify-center gap-2 mt-4">
          {['analyze', 'layouts', 'perspective', 'chat'].map((s, i) => (
            <div
              key={s}
              className={`w-2 h-2 rounded-full transition-colors ${state.stage === s ? 'bg-[#6b7aa1]' : 'bg-gray-300'
                }`}
            />
          ))}
        </div>
      </header>

      {/* === Main Content === */}
      <main className="max-w-7xl mx-auto px-4 pb-8">
        <div className="card p-4 md:p-6">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
