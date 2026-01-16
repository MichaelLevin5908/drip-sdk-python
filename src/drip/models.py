"""
Drip SDK data models using Pydantic.

This module contains all the data models and types used by the Drip SDK,
mirroring the TypeScript SDK's type definitions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Enums
# =============================================================================


class ChargeStatus(str, Enum):
    """Status of a charge."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class CustomerStatus(str, Enum):
    """Status of a customer."""

    ACTIVE = "ACTIVE"
    LOW_BALANCE = "LOW_BALANCE"
    PAUSED = "PAUSED"


class RunStatus(str, Enum):
    """Status of an agent run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class ProductSurface(str, Enum):
    """Product surface type for workflows."""

    RPC = "RPC"
    WEBHOOK = "WEBHOOK"
    AGENT = "AGENT"
    PIPELINE = "PIPELINE"
    CUSTOM = "CUSTOM"


class WebhookEventType(str, Enum):
    """Types of webhook events that can be subscribed to."""

    CUSTOMER_BALANCE_LOW = "customer.balance.low"
    USAGE_RECORDED = "usage.recorded"
    CHARGE_SUCCEEDED = "charge.succeeded"
    CHARGE_FAILED = "charge.failed"
    CUSTOMER_DEPOSIT_CONFIRMED = "customer.deposit.confirmed"
    CUSTOMER_WITHDRAW_CONFIRMED = "customer.withdraw.confirmed"
    CUSTOMER_USAGE_CAP_REACHED = "customer.usage_cap.reached"
    WEBHOOK_ENDPOINT_UNHEALTHY = "webhook.endpoint.unhealthy"
    CUSTOMER_CREATED = "customer.created"
    API_KEY_CREATED = "api_key.created"
    PRICING_PLAN_UPDATED = "pricing_plan.updated"
    TRANSACTION_CREATED = "transaction.created"
    TRANSACTION_PENDING = "transaction.pending"
    TRANSACTION_CONFIRMED = "transaction.confirmed"
    TRANSACTION_FAILED = "transaction.failed"


# =============================================================================
# Configuration
# =============================================================================


class DripConfig(BaseModel):
    """Configuration for the Drip client."""

    model_config = ConfigDict(frozen=True)

    api_key: str = Field(..., description="API key from Drip dashboard")
    base_url: str = Field(
        default="https://api.drip.dev/v1", description="Base URL for the Drip API"
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds")


# =============================================================================
# Customer Models
# =============================================================================


class CreateCustomerParams(BaseModel):
    """Parameters for creating a new customer."""

    onchain_address: str = Field(
        ..., alias="onchainAddress", description="Customer's smart account address"
    )
    external_customer_id: str | None = Field(
        default=None, alias="externalCustomerId", description="Your internal customer ID"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="Custom metadata")

    model_config = ConfigDict(populate_by_name=True)


class Customer(BaseModel):
    """Customer record."""

    id: str
    business_id: str = Field(alias="businessId")
    external_customer_id: str | None = Field(alias="externalCustomerId")
    onchain_address: str = Field(alias="onchainAddress")
    metadata: dict[str, Any] | None = None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class ListCustomersOptions(BaseModel):
    """Options for listing customers."""

    status: CustomerStatus | None = None
    limit: int = Field(default=100, ge=1, le=100)


class ListCustomersResponse(BaseModel):
    """Response from listing customers."""

    data: list[Customer]
    count: int


class BalanceResult(BaseModel):
    """Balance information for a customer."""

    customer_id: str = Field(alias="customerId")
    onchain_address: str = Field(alias="onchainAddress")
    balance_usdc: str = Field(alias="balanceUsdc", description="Balance in USDC (6 decimals)")
    pending_charges_usdc: str = Field(alias="pendingChargesUsdc")
    available_usdc: str = Field(alias="availableUsdc")
    last_synced_at: str | None = Field(alias="lastSyncedAt")

    model_config = ConfigDict(populate_by_name=True)


# =============================================================================
# Charge Models
# =============================================================================


class ChargeParams(BaseModel):
    """Parameters for creating a charge."""

    customer_id: str = Field(alias="customerId")
    meter: str = Field(..., description="Usage meter type (e.g., 'api_calls', 'tokens')")
    quantity: float
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class ChargeInfo(BaseModel):
    """Charge information within a ChargeResult."""

    id: str
    amount_usdc: str = Field(alias="amountUsdc")
    amount_token: str = Field(alias="amountToken")
    tx_hash: str = Field(alias="txHash")
    status: ChargeStatus

    model_config = ConfigDict(populate_by_name=True)


class ChargeResult(BaseModel):
    """Result of a charge operation."""

    success: bool
    usage_event_id: str = Field(alias="usageEventId")
    is_replay: bool = Field(alias="isReplay", description="True if idempotent replay")
    charge: ChargeInfo

    model_config = ConfigDict(populate_by_name=True)


class TrackUsageResult(BaseModel):
    """Result of tracking usage without billing."""

    success: bool
    usage_event_id: str = Field(alias="usageEventId")
    customer_id: str = Field(alias="customerId")
    usage_type: str = Field(alias="usageType")
    quantity: float
    is_internal: bool = Field(alias="isInternal")
    message: str

    model_config = ConfigDict(populate_by_name=True)


class ChargeCustomer(BaseModel):
    """Customer info within a Charge."""

    id: str
    onchain_address: str = Field(alias="onchainAddress")
    external_customer_id: str | None = Field(alias="externalCustomerId")

    model_config = ConfigDict(populate_by_name=True)


class ChargeUsageEvent(BaseModel):
    """Usage event info within a Charge."""

    id: str
    type: str
    quantity: str
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class Charge(BaseModel):
    """Full charge record."""

    id: str
    usage_id: str = Field(alias="usageId")
    customer_id: str = Field(alias="customerId")
    customer: ChargeCustomer
    usage_event: ChargeUsageEvent = Field(alias="usageEvent")
    amount_usdc: str = Field(alias="amountUsdc")
    amount_token: str = Field(alias="amountToken")
    tx_hash: str | None = Field(alias="txHash")
    block_number: str | None = Field(alias="blockNumber")
    status: ChargeStatus
    failure_reason: str | None = Field(alias="failureReason")
    created_at: str = Field(alias="createdAt")
    confirmed_at: str | None = Field(alias="confirmedAt")

    model_config = ConfigDict(populate_by_name=True)


class ListChargesOptions(BaseModel):
    """Options for listing charges."""

    customer_id: str | None = Field(default=None, alias="customerId")
    status: ChargeStatus | None = None
    limit: int = Field(default=100, ge=1, le=100)


class ListChargesResponse(BaseModel):
    """Response from listing charges."""

    data: list[Charge]
    count: int


class ChargeStatusResult(BaseModel):
    """Quick charge status check result."""

    status: ChargeStatus
    tx_hash: str | None = Field(default=None, alias="txHash")

    model_config = ConfigDict(populate_by_name=True)


# =============================================================================
# Checkout Models
# =============================================================================


class CheckoutParams(BaseModel):
    """Parameters for creating a checkout session."""

    customer_id: str | None = Field(default=None, alias="customerId")
    external_customer_id: str | None = Field(default=None, alias="externalCustomerId")
    amount: int = Field(..., description="Amount in cents (5000 = $50.00)")
    return_url: str = Field(alias="returnUrl")
    cancel_url: str | None = Field(default=None, alias="cancelUrl")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class CheckoutResult(BaseModel):
    """Result of creating a checkout session."""

    id: str
    url: str = Field(..., description="Hosted checkout URL")
    expires_at: str = Field(alias="expiresAt")
    amount_usd: float = Field(alias="amountUsd")

    model_config = ConfigDict(populate_by_name=True)


# =============================================================================
# Webhook Models
# =============================================================================


class CreateWebhookParams(BaseModel):
    """Parameters for creating a webhook."""

    url: str = Field(..., description="HTTPS endpoint")
    events: list[WebhookEventType]
    description: str | None = None


class WebhookStats(BaseModel):
    """Webhook delivery statistics."""

    total_deliveries: int = Field(alias="totalDeliveries")
    successful_deliveries: int = Field(alias="successfulDeliveries")
    failed_deliveries: int = Field(alias="failedDeliveries")
    last_delivery_at: str | None = Field(alias="lastDeliveryAt")

    model_config = ConfigDict(populate_by_name=True)


class Webhook(BaseModel):
    """Webhook record."""

    id: str
    url: str
    events: list[str]
    description: str | None = None
    is_active: bool = Field(alias="isActive")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    stats: WebhookStats | None = None

    model_config = ConfigDict(populate_by_name=True)


class CreateWebhookResponse(Webhook):
    """Response from creating a webhook (includes secret)."""

    secret: str = Field(..., description="Only returned once - store securely!")
    message: str


class ListWebhooksResponse(BaseModel):
    """Response from listing webhooks."""

    data: list[Webhook]
    count: int


class DeleteWebhookResponse(BaseModel):
    """Response from deleting a webhook."""

    message: str
    deleted: bool


class TestWebhookResponse(BaseModel):
    """Response from testing a webhook."""

    message: str
    delivery_id: str | None = Field(alias="deliveryId")
    status: str

    model_config = ConfigDict(populate_by_name=True)


class RotateWebhookSecretResponse(BaseModel):
    """Response from rotating a webhook secret."""

    secret: str
    message: str


# =============================================================================
# Workflow & Run Models
# =============================================================================


class CreateWorkflowParams(BaseModel):
    """Parameters for creating a workflow."""

    name: str
    slug: str = Field(..., description="URL-safe identifier")
    product_surface: ProductSurface | None = Field(default=None, alias="productSurface")
    description: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class Workflow(BaseModel):
    """Workflow record."""

    id: str
    name: str
    slug: str
    product_surface: str = Field(alias="productSurface")
    description: str | None = None
    is_active: bool = Field(alias="isActive")
    created_at: str = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class ListWorkflowsResponse(BaseModel):
    """Response from listing workflows."""

    data: list[Workflow]
    count: int


class StartRunParams(BaseModel):
    """Parameters for starting an agent run."""

    customer_id: str = Field(alias="customerId")
    workflow_id: str = Field(alias="workflowId")
    external_run_id: str | None = Field(default=None, alias="externalRunId")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    parent_run_id: str | None = Field(default=None, alias="parentRunId")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class RunResult(BaseModel):
    """Result of starting a run."""

    id: str
    customer_id: str = Field(alias="customerId")
    workflow_id: str = Field(alias="workflowId")
    workflow_name: str = Field(alias="workflowName")
    status: RunStatus
    correlation_id: str | None = Field(alias="correlationId")
    created_at: str = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class EndRunParams(BaseModel):
    """Parameters for ending a run."""

    status: Literal["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"]
    error_message: str | None = Field(default=None, alias="errorMessage")
    error_code: str | None = Field(default=None, alias="errorCode")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class EndRunResult(BaseModel):
    """Result of ending a run."""

    id: str
    status: RunStatus
    ended_at: str = Field(alias="endedAt")
    duration_ms: int | None = Field(alias="durationMs")
    event_count: int = Field(alias="eventCount")
    total_cost_units: str | None = Field(alias="totalCostUnits")

    model_config = ConfigDict(populate_by_name=True)


class EmitEventParams(BaseModel):
    """Parameters for emitting an event within a run."""

    run_id: str = Field(alias="runId")
    event_type: str = Field(alias="eventType")
    quantity: float | None = None
    units: str | None = None
    description: str | None = None
    cost_units: float | None = Field(default=None, alias="costUnits")
    cost_currency: str | None = Field(default=None, alias="costCurrency")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    parent_event_id: str | None = Field(default=None, alias="parentEventId")
    span_id: str | None = Field(default=None, alias="spanId")
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class EventResult(BaseModel):
    """Result of emitting an event."""

    id: str
    run_id: str = Field(alias="runId")
    event_type: str = Field(alias="eventType")
    quantity: float
    cost_units: float | None = Field(alias="costUnits")
    is_duplicate: bool = Field(alias="isDuplicate")
    timestamp: str

    model_config = ConfigDict(populate_by_name=True)


class EmitEventsBatchResult(BaseModel):
    """Result of batch event emission."""

    success: bool
    created: int
    duplicates: int
    events: list[EventResult]


class TimelineEventCharge(BaseModel):
    """Charge info within a timeline event."""

    id: str
    amount_usdc: str = Field(alias="amountUsdc")
    status: str

    model_config = ConfigDict(populate_by_name=True)


class TimelineEvent(BaseModel):
    """Event in a run timeline."""

    id: str
    event_type: str = Field(alias="eventType")
    quantity: float
    units: str | None = None
    description: str | None = None
    cost_units: float | None = Field(alias="costUnits")
    timestamp: str
    correlation_id: str | None = Field(alias="correlationId")
    parent_event_id: str | None = Field(alias="parentEventId")
    charge: TimelineEventCharge | None = None

    model_config = ConfigDict(populate_by_name=True)


class TimelineRunInfo(BaseModel):
    """Run info within a timeline."""

    id: str
    customer_id: str = Field(alias="customerId")
    customer_name: str | None = Field(alias="customerName")
    workflow_id: str = Field(alias="workflowId")
    workflow_name: str = Field(alias="workflowName")
    status: RunStatus
    started_at: str | None = Field(alias="startedAt")
    ended_at: str | None = Field(alias="endedAt")
    duration_ms: int | None = Field(alias="durationMs")
    error_message: str | None = Field(alias="errorMessage")
    error_code: str | None = Field(alias="errorCode")
    correlation_id: str | None = Field(alias="correlationId")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class TimelineTotals(BaseModel):
    """Totals for a run timeline."""

    event_count: int = Field(alias="eventCount")
    total_quantity: str = Field(alias="totalQuantity")
    total_cost_units: str = Field(alias="totalCostUnits")
    total_charged_usdc: str = Field(alias="totalChargedUsdc")

    model_config = ConfigDict(populate_by_name=True)


class RunTimeline(BaseModel):
    """Full timeline for a run."""

    run: TimelineRunInfo
    timeline: list[TimelineEvent]
    totals: TimelineTotals
    summary: str


# =============================================================================
# Record Run (Simplified API)
# =============================================================================


class RecordRunEvent(BaseModel):
    """Event to record within a run (simplified API)."""

    event_type: str = Field(alias="eventType")
    quantity: float | None = None
    units: str | None = None
    description: str | None = None
    cost_units: float | None = Field(default=None, alias="costUnits")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class RecordRunParams(BaseModel):
    """Parameters for the simplified record_run API."""

    customer_id: str = Field(alias="customerId")
    workflow: str = Field(..., description="Workflow ID or slug (auto-creates if slug)")
    events: list[RecordRunEvent]
    status: Literal["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"]
    error_message: str | None = Field(default=None, alias="errorMessage")
    error_code: str | None = Field(default=None, alias="errorCode")
    external_run_id: str | None = Field(default=None, alias="externalRunId")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class RecordRunResultRun(BaseModel):
    """Run info in record run result."""

    id: str
    workflow_id: str = Field(alias="workflowId")
    workflow_name: str = Field(alias="workflowName")
    status: RunStatus
    duration_ms: int | None = Field(alias="durationMs")

    model_config = ConfigDict(populate_by_name=True)


class RecordRunResultEvents(BaseModel):
    """Event stats in record run result."""

    created: int
    duplicates: int


class RecordRunResult(BaseModel):
    """Result of the simplified record_run API."""

    run: RecordRunResultRun
    events: RecordRunResultEvents
    total_cost_units: str | None = Field(alias="totalCostUnits")
    summary: str

    model_config = ConfigDict(populate_by_name=True)


# =============================================================================
# Meter Models
# =============================================================================


class Meter(BaseModel):
    """Usage meter configuration."""

    id: str
    name: str
    meter: str = Field(..., description="Use this in charge() calls")
    unit_price_usd: str = Field(alias="unitPriceUsd")
    is_active: bool = Field(alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class ListMetersResponse(BaseModel):
    """Response from listing meters."""

    data: list[Meter]
    count: int


# =============================================================================
# x402 Payment Protocol Models
# =============================================================================


class X402PaymentProof(BaseModel):
    """Payment proof submitted by client for x402 protocol."""

    signature: str
    session_key_id: str = Field(alias="sessionKeyId")
    smart_account: str = Field(alias="smartAccount")
    timestamp: int
    amount: str
    recipient: str
    usage_id: str = Field(alias="usageId")
    nonce: str

    model_config = ConfigDict(populate_by_name=True)


class X402PaymentRequest(BaseModel):
    """Payment request returned in 402 response."""

    amount: str
    recipient: str
    usage_id: str = Field(alias="usageId")
    description: str
    expires_at: int = Field(alias="expiresAt")
    nonce: str
    timestamp: int

    model_config = ConfigDict(populate_by_name=True)


# =============================================================================
# Idempotency Key Generation
# =============================================================================


class IdempotencyKeyParams(BaseModel):
    """Parameters for generating idempotency keys."""

    customer_id: str = Field(alias="customerId")
    run_id: str | None = Field(default=None, alias="runId")
    step_name: str = Field(alias="stepName")
    sequence: int | None = None

    model_config = ConfigDict(populate_by_name=True)
