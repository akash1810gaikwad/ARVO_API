# API Authentication Requirements

This document outlines which API endpoints require authentication tokens and which are publicly accessible.


## Authentication Method
- **Type**: Bearer Token (JWT)
- **Header Format**: `Authorization: Bearer {token}`
- **Token Storage**: Client stores token in localStorage after successful login

---

## Public Endpoints (No Authentication Required)

These endpoints can be accessed without an authentication token.

### 1. Plans API

#### Get All Plans
```
GET /plans/
```
**Query Parameters:**
- `skip` (optional): Number of records to skip
- `limit` (optional): Maximum number of records to return
- `active_only` (optional): Filter for active plans only

**Response**: Array of plan objects

#### Get Plan by ID
```
GET /plans/{id}
```
**Response**: Single plan object

---

### 2. Authentication & Registration

#### Google OAuth Login
```
POST /customers/auth/google
```
**Request Body:**
```json
{
  "token": "string"
}
```
**Response:**
```json
{
  "access_token": "string",
  "token_type": "Bearer",
  "customer": { ... }
}
```

#### Create Customer (Registration)
```
POST /customers/
```
**Request Body:**
```json
{
  "email": "string",
  "full_name": "string",
  "phone_number": "string (optional)",
  "address": "string (optional)",
  "postcode": "string (optional)",
  "city": "string (optional)",
  "country": "string (optional)",
  "number_of_children": "number (optional)",
  "password": "string (optional)"
}
```
**Response**: Customer object

#### Email/Password Login
```
POST /customers/auth/login
```
**Request Body:**
```json
{
  "email": "string",
  "password": "string"
}
```
**Response:**
```json
{
  "access_token": "string",
  "token_type": "Bearer",
  "customer": { ... }
}
```

#### Verify Email
```
POST /customers/verify-email
```
**Request Body:**
```json
{
  "token": "string"
}
```
**Response:**
```json
{
  "message": "string",
  "is_verified": true
}
```

#### Forgot Password (Request OTP)
```
POST /customers/forgot-password
```
**Request Body:**
```json
{
  "email": "string"
}
```
**Response:**
```json
{
  "message": "string"
}
```

#### Reset Password (With OTP)
```
POST /customers/reset-password
```
**Request Body:**
```json
{
  "email": "string",
  "otp": "string",
  "new_password": "string"
}
```
**Response:**
```json
{
  "message": "string"
}
```

---

### 3. Promo Code Validation

#### Validate Promo Code
```
POST /v1/promo-codes/validate/{code}
```
**Response:**
```json
{
  "valid": true,
  "message": "string",
  "promo_code": {
    "id": 1,
    "code": "string",
    "description": "string",
    "discount_type": "PERCENTAGE | FIXED_AMOUNT",
    "discount_value": 10,
    "bypass_payment": false,
    "activate_sim": false,
    "max_uses": 100,
    "used_count": 5,
    "valid_from": "2024-01-01T00:00:00",
    "valid_until": "2024-12-31T23:59:59",
    "is_active": true
  }
}
```

---

## Protected Endpoints (Authentication Required)

These endpoints require a valid JWT token in the Authorization header.

### 1. Customer Management

#### Get Current User
```
GET /customers/me
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: Customer object

#### Get Customer by ID
```
GET /customers/{customerId}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: Customer object

#### Update Customer
```
PUT /customers/{customerId}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Request Body**: Partial customer object with fields to update
**Response**: Updated customer object

---

### 2. User Profile

#### Get User Profile
```
GET /users/profile
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: User profile object

#### Update User Profile
```
PUT /users/profile
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Request Body**: Profile data to update
**Response**: Updated profile object

---

### 3. SIM Management

#### Get All SIMs
```
GET /sims
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: Array of SIM objects

#### Get SIM by ID
```
GET /sims/{id}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: Single SIM object

#### Create SIM
```
POST /sims
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Request Body**: SIM data
**Response**: Created SIM object

#### Update SIM
```
PUT /sims/{id}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Request Body**: SIM data to update
**Response**: Updated SIM object

#### Delete SIM
```
DELETE /sims/{id}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: Success confirmation

---

### 4. Subscription Management

#### Create Subscription
```
POST /new-subscriptions/create
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Request Body:**
```json
{
  "customer_id": 1,
  "plan_id": 1,
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "children": [
    {
      "name": "string",
      "age": 10
    }
  ],
  "currency": "GBP",
  "auto_renew": true,
  "payment_method_id": "string",
  "sim_type": "pSIM | eSIM",
  "promo_code": "string (optional)"
}
```
**Response:**
```json
{
  "subscription_id": 1,
  "subscription_number": "string",
  "status": "string",
  "is_test_order": false,
  "payment_method": "string"
}
```

#### Check Customer Subscription
```
GET /new-subscriptions/subscriber/check/{customerId}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: Subscriber info object

#### Get Invoice History
```
GET /new-subscriptions/invoices/customer/{customerId}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: Array of invoice objects

#### Get Billing Summary
```
GET /new-subscriptions/customer/{customerId}/billing-summary
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response:**
```json
{
  "customer_id": 1,
  "is_subscriber": true,
  "current_plan": { ... },
  "latest_sim_cards": [ ... ],
  "total_sim_cards": 3,
  "total_spend": 299.99,
  "currency": "GBP",
  "current_billing": { ... },
  "next_billing": { ... }
}
```

#### Get Children SIM Cards
```
GET /customers/{customerId}/children-sims
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response:**
```json
{
  "customer_id": 1,
  "customer_name": "string",
  "customer_email": "string",
  "total_children": 3,
  "active_sims": 2,
  "inactive_sims": 1,
  "children_sims": [ ... ]
}
```

#### Download Receipt PDF
```
GET /new-subscriptions/invoice/pdf/{paymentIntentId}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Response**: PDF file download

---

### 5. Parental Controls

#### Get Parental Controls
```
GET /parental-controls/child/{childSimCardId}?customer_id={customerId}&plan_id={planId}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Query Parameters:**
- `customer_id` (required)
- `plan_id` (required)

**Response:**
```json
{
  "child_sim_card_id": 1,
  "child_name": "string",
  "sim_number": "string",
  "iccid": "string",
  "has_custom_settings": true,
  "settings_source": "string",
  "params": [
    {
      "name": "string",
      "value": "on | off"
    }
  ],
  "previous_params": [ ... ],
  "last_synced_at": "2024-01-01T00:00:00",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### Update Parental Controls
```
PUT /parental-controls/child/{childSimCardId}?customer_id={customerId}&sync_with_transatel={true|false}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Query Parameters:**
- `customer_id` (required)
- `sync_with_transatel` (optional, default: true)

**Request Body:**
```json
{
  "params": [
    {
      "name": "string",
      "value": "on | off"
    }
  ]
}
```
**Response**: Updated parental controls object

#### Create Parental Controls
```
POST /parental-controls
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Request Body:**
```json
{
  "child_sim_card_id": 1,
  "params": [
    {
      "name": "string",
      "value": "on | off"
    }
  ],
  "sync_with_transatel": true
}
```
**Response**: Created parental controls object

#### Sync Parental Controls
```
POST /parental-controls/sync?customer_id={customerId}
```
**Headers Required:**
```
Authorization: Bearer {token}
```
**Query Parameters:**
- `customer_id` (required)

**Response:**
```json
{
  "message": "string",
  "synced_count": 3
}
```

---

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "message": "Error description",
  "detail": "Additional error details (optional)"
}
```

### Common HTTP Status Codes:
- `200` - Success
- `201` - Created
- `204` - No Content (successful deletion)
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (missing or invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

---

## Authentication Flow

1. **User Registration/Login**
   - Call `/customers/` (registration) or `/customers/auth/login` or `/customers/auth/google`
   - Receive `access_token` in response
   - Store token securely (localStorage/sessionStorage)

2. **Making Authenticated Requests**
   - Include token in Authorization header: `Authorization: Bearer {token}`
   - Token is validated on each request

3. **Token Expiration**
   - If token expires, API returns 401 Unauthorized
   - Client should redirect to login page
   - User must re-authenticate to get new token

4. **Logout**
   - Remove token from client storage
   - No server-side logout endpoint needed (stateless JWT)
