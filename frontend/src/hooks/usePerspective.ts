'use client';

import { useState, useCallback } from 'react';
import { generatePerspective } from '@/lib/api';
import type { PerspectiveRequest, PerspectiveResponse } from '@/lib/types';

export function usePerspective() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<PerspectiveResponse | null>(null);

    const generate = useCallback(async (request: PerspectiveRequest) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await generatePerspective(request);
            setData(response);
            return response;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Perspective generation failed';
            setError(message);
            throw new Error(message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const reset = useCallback(() => {
        setData(null);
        setError(null);
    }, []);

    return { generate, isLoading, error, data, reset };
}
