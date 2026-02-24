/**
 * Builds the Intercom inbox URL for a conversation.
 * Set VITE_INTERCOM_APP_ID in your env to enable "Open in Intercom" links.
 * App ID can be found in the Intercom dashboard URL when viewing the inbox.
 */
const INTERCOM_APP_ID = import.meta.env.VITE_INTERCOM_APP_ID as string | undefined

const INTERCOM_CONVERSATION_BASE = INTERCOM_APP_ID
  ? `https://app.intercom.com/a/inbox/${INTERCOM_APP_ID}/inbox/shared/all/conversation`
  : null

export function getIntercomConversationUrl(conversationId: string): string | null {
  if (!INTERCOM_CONVERSATION_BASE || !conversationId) return null
  return `${INTERCOM_CONVERSATION_BASE}/${conversationId}`
}

export function hasIntercomLink(): boolean {
  return INTERCOM_CONVERSATION_BASE !== null
}
