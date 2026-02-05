'use client';

import { useState, useCallback } from 'react';
import { chatEdit } from '@/lib/api';
import type { ChatEditRequest, ChatEditResponse } from '@/lib/types';

interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

export function useChatEdit() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);

    const sendCommand = useCallback(async (request: ChatEditRequest) => {
        setIsLoading(true);
        setError(null);

        // Add user message
        setMessages(prev => [...prev, {
            role: 'user',
            content: request.command,
            timestamp: new Date()
        }]);

        try {
            const response = await chatEdit(request);

            // Add assistant response
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: response.explanation,
                timestamp: new Date()
            }]);

            return response;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Chat edit failed';
            setError(message);

            // Add error message
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `Error: ${message}`,
                timestamp: new Date()
            }]);

            throw new Error(message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const reset = useCallback(() => {
        setMessages([]);
        setError(null);
    }, []);

    return { sendCommand, isLoading, error, messages, reset };
}
