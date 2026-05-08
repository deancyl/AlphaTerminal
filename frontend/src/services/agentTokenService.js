/**
 * Agent Token Service - API Client for Token Management
 * 
 * Provides CRUD operations for Agent API Tokens
 */

import { apiFetch } from '../utils/api.js'

const BASE_URL = '/api/agent/v1'

/**
 * List all tokens
 * @param {boolean} includeInactive - Include revoked/expired tokens
 * @returns {Promise<Array>} List of tokens
 */
export async function listTokens(includeInactive = false) {
  const url = `${BASE_URL}/admin/tokens${includeInactive ? '?include_inactive=true' : ''}`
  const data = await apiFetch(url, {
    headers: {
      'X-Admin-Auth': 'admin_ui' // Simple admin auth for UI
    }
  })
  return data
}

/**
 * Create a new token
 * @param {Object} params - Token creation parameters
 * @param {string} params.name - Token name
 * @param {string[]} params.scopes - Permission scopes (R/W/B/N/C/T)
 * @param {string[]} [params.markets] - Allowed markets
 * @param {number} [params.rate_limit] - Rate limit per minute
 * @param {number} [params.expires_in_days] - Expiry in days (null = never)
 * @returns {Promise<Object>} Created token with raw token string
 */
export async function createToken(params) {
  const url = `${BASE_URL}/admin/tokens`
  const data = await apiFetch(url, {
    method: 'POST',
    body: JSON.stringify({
      name: params.name,
      scopes: params.scopes || ['R'],
      markets: params.markets || null,
      rate_limit: params.rate_limit || 120,
      expires_in_days: params.expires_in_days ?? 30,
      paper_only: true, // Always paper trading for safety
    }),
    headers: {
      'X-Admin-Auth': 'admin_ui'
    }
  })
  return data
}

/**
 * Revoke a token
 * @param {string} tokenId - Token ID to revoke
 * @returns {Promise<Object>} Result
 */
export async function revokeToken(tokenId) {
  const url = `${BASE_URL}/admin/tokens/${tokenId}`
  const data = await apiFetch(url, {
    method: 'DELETE',
    headers: {
      'X-Admin-Auth': 'admin_ui'
    }
  })
  return data
}

/**
 * Verify token identity (whoami)
 * @param {string} token - Raw token string
 * @returns {Promise<Object>} Token info
 */
export async function verifyToken(token) {
  const url = `${BASE_URL}/whoami`
  const data = await apiFetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  return data
}

// Scope labels for display
export const SCOPE_LABELS = {
  R: '读取',
  W: '写入',
  B: '回测',
  N: '通知',
  C: '凭证',
  T: '交易',
}

// Scope colors for badges
export const SCOPE_COLORS = {
  R: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  W: 'bg-green-500/20 text-green-400 border-green-500/30',
  B: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  N: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  C: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  T: 'bg-red-500/20 text-red-400 border-red-500/30',
}
