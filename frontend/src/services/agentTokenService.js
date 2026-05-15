/**
 * Agent Token Service - API Client for Token Management
 * 
 * Provides CRUD operations for Agent API Tokens
 */

import { apiFetch } from '../utils/api.js'

const BASE_URL = '/api/agent/v1'
const ADMIN_TOKEN_KEY = 'admin_jwt_token'
const ADMIN_TOKEN_EXPIRY_KEY = 'admin_jwt_expiry'

/**
 * Get admin JWT token from localStorage or fetch new one
 * @returns {Promise<string|null>} JWT token or null if not configured
 */
async function getAdminSessionToken() {
  const storedToken = localStorage.getItem(ADMIN_TOKEN_KEY)
  const storedExpiry = localStorage.getItem(ADMIN_TOKEN_EXPIRY_KEY)
  
  // Check if token exists and is not expired
  if (storedToken && storedExpiry) {
    const expiryTime = new Date(storedExpiry).getTime()
    const now = Date.now()
    // Refresh 1 hour before expiry
    const refreshThreshold = expiryTime - (60 * 60 * 1000)
    
    if (now < refreshThreshold) {
      return storedToken
    }
  }
  
  // Fetch new JWT token from backend
  const adminApiKey = import.meta.env.VITE_ADMIN_API_KEY || ''
  
  if (!adminApiKey) {
    console.warn('[AgentTokenService] VITE_ADMIN_API_KEY not configured, admin access disabled')
    return null
  }
  
  try {
    const response = await apiFetch('/api/v1/admin/token', {
      method: 'POST',
      headers: {
        'X-Admin-Api-Key': adminApiKey
      }
    })
    
    if (response.code === 0 && response.data?.token) {
      const token = response.data.token
      const expiresAt = response.data.expires_at
      
      localStorage.setItem(ADMIN_TOKEN_KEY, token)
      localStorage.setItem(ADMIN_TOKEN_EXPIRY_KEY, expiresAt)
      
      console.log('[AgentTokenService] JWT token refreshed, expires at', expiresAt)
      return token
    }
  } catch (error) {
    console.error('[AgentTokenService] Failed to get JWT token:', error)
  }
  
  return null
}

/**
 * Validate current JWT token
 * @returns {Promise<boolean>} True if valid
 */
async function validateSessionToken() {
  const storedToken = localStorage.getItem(ADMIN_TOKEN_KEY)
  if (!storedToken) return false
  
  try {
    const response = await apiFetch('/api/v1/admin/token/validate', {
      headers: {
        'X-Admin-Token': storedToken
      }
    })
    return response.code === 0 && response.data?.valid === true
  } catch (error) {
    console.error('[AgentTokenService] Token validation failed:', error)
    return false
  }
}

/**
 * Clear stored JWT token
 */
function clearSessionToken() {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
  localStorage.removeItem(ADMIN_TOKEN_EXPIRY_KEY)
}

/**
 * List all tokens
 * @param {boolean} includeInactive - Include revoked/expired tokens
 * @returns {Promise<Array>} List of tokens
 */
export async function listTokens(includeInactive = false) {
  const sessionToken = await getAdminSessionToken()
  const url = `${BASE_URL}/admin/tokens${includeInactive ? '?include_inactive=true' : ''}`
  const data = await apiFetch(url, {
    headers: {
      'X-Admin-Auth': sessionToken
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
  const sessionToken = await getAdminSessionToken()
  const url = `${BASE_URL}/admin/tokens`
  const data = await apiFetch(url, {
    method: 'POST',
    body: JSON.stringify({
      name: params.name,
      scopes: params.scopes || ['R'],
      markets: params.markets || null,
      rate_limit: params.rate_limit || 120,
      expires_in_days: params.expires_in_days ?? 30,
      paper_only: true,
    }),
    headers: {
      'X-Admin-Auth': sessionToken
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
  const sessionToken = await getAdminSessionToken()
  const url = `${BASE_URL}/admin/tokens/${tokenId}`
  const data = await apiFetch(url, {
    method: 'DELETE',
    headers: {
      'X-Admin-Auth': sessionToken
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

// Export session management functions
export { getAdminSessionToken, validateSessionToken, clearSessionToken }
