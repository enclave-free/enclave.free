import { describe, expect, it } from 'vitest';
import * as chat from './index';

describe('chat public API', () => {
  it('exposes the assistant-ui Conversation surface instead of the retired bespoke MessageList thread', () => {
    expect(chat).toHaveProperty('ConversationSurface');
    expect(chat).toHaveProperty('UserConversation');
    expect(chat).toHaveProperty('AssistantConversationThread');
    expect(chat).toHaveProperty('getConversationMessageActions');
    expect(chat).not.toHaveProperty('MessageList');
  });
});
