/*
 * Cognito auth helpers using amazon-cognito-identity-js
 */

import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
} from 'amazon-cognito-identity-js'

const POOL_DATA = {
  UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
  ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
}

const userPool = new CognitoUserPool(POOL_DATA)

export function login(email, password) {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool })
    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    })

    user.authenticateUser(authDetails, {
      onSuccess: (result) => {
        const idToken = result.getIdToken().getJwtToken()
        const accessToken = result.getAccessToken().getJwtToken()
        sessionStorage.setItem('idToken', idToken)
        sessionStorage.setItem('accessToken', accessToken)
        sessionStorage.setItem('userEmail', email)
        resolve({ idToken, email })
      },
      onFailure: (err) => reject(err),
      newPasswordRequired: (userAttributes) => {
        // First-time login — Cognito requires password change
        // For simplicity, use the same password
        delete userAttributes.email_verified
        delete userAttributes.email
        user.completeNewPasswordChallenge(password, userAttributes, {
          onSuccess: (result) => {
            const idToken = result.getIdToken().getJwtToken()
            sessionStorage.setItem('idToken', idToken)
            sessionStorage.setItem('userEmail', email)
            resolve({ idToken, email })
          },
          onFailure: (err) => reject(err),
        })
      },
    })
  })
}

export function logout() {
  const user = userPool.getCurrentUser()
  if (user) user.signOut()
  sessionStorage.clear()
}

export function getCurrentUser() {
  return sessionStorage.getItem('userEmail')
}

export function isLoggedIn() {
  return !!sessionStorage.getItem('idToken')
}
