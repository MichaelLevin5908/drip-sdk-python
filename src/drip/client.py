"""
Drip SDK client.

This module provides the main Drip client class for interacting with
the Drip API for usage-based billing with on-chain settlement.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .errors import (
    DripAuthenticationError,
    DripNetworkError,
    create_api_error_from_response,
)
from .models import (
    BalanceResult,
    Charge,
    ChargeResult,
    ChargeStatusResult,
    CheckoutResult,
    CreateWebhookResponse,
    Customer,
    CustomerStatus,
    DeleteWebhookResponse,
    DripConfig,
    EmitEventsBatchResult,
    EndRunResult,
    EventResult,
    ListChargesResponse,
    ListCustomersResponse,
    ListMetersResponse,
    ListWebhooksResponse,
    ListWorkflowsResponse,
    RecordRunResult,
    RotateWebhookSecretResponse,
    RunResult,
    RunTimeline,
    TestWebhookResponse,
    Webhook,
    Workflow,
)
from .stream import StreamMeter, StreamMeterOptions
from .utils import generate_idempotency_key, verify_webhook_signature


class Drip:
    """
    Official Python SDK client for Drip - usage-based billing with on-chain settlement.

    The Drip client provides methods for:
    - Customer management (create, list, get balance)
    - Charging (create charges, check status)
    - Checkout (fiat on-ramp)
    - Webhooks (create, manage, verify)
    - Agent run tracking (workflows, runs, events)
    - Meters (pricing configuration)

    Example:
        >>> from drip import Drip
        >>>
        >>> client = Drip(api_key="drip_sk_...")
        >>>
        >>> # Create a customer
        >>> customer = client.create_customer(
        ...     onchain_address="0x123...",
        ...     external_customer_id="user_123"
        ... )
        >>>
        >>> # Create a charge
        >>> result = client.charge(
        ...     customer_id=customer.id,
        ...     meter="api_calls",
        ...     quantity=1
        ... )
    """

    DEFAULT_BASE_URL = "https://api.drip.dev/v1"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """
        Initialize the Drip client.

        Args:
            api_key: API key from Drip dashboard. If not provided,
                     reads from DRIP_API_KEY environment variable.
            base_url: Base URL for the API. Defaults to https://api.drip.dev/v1.
                      Can also be set via DRIP_API_URL environment variable.
            timeout: Request timeout in seconds. Defaults to 30.

        Raises:
            DripAuthenticationError: If no API key is provided or found in environment.
        """
        self._api_key = api_key or os.environ.get("DRIP_API_KEY")
        if not self._api_key:
            raise DripAuthenticationError(
                "API key is required. Pass it directly or set DRIP_API_KEY environment variable."
            )

        self._base_url = (
            base_url or os.environ.get("DRIP_API_URL") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self._timeout = timeout or self.DEFAULT_TIMEOUT

        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "drip-sdk-python/1.0.0",
            },
        )

    def __enter__(self) -> Drip:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._client.close()

    @property
    def config(self) -> DripConfig:
        """Get the current configuration."""
        # api_key is guaranteed to be non-None after __init__
        assert self._api_key is not None
        return DripConfig(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )

    # =========================================================================
    # HTTP Request Helpers
    # =========================================================================

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API endpoint path.
            json: JSON body for POST/PUT requests.
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            DripAPIError: For API errors.
            DripNetworkError: For network errors.
        """
        try:
            response = self._client.request(
                method=method,
                url=path,
                json=json,
                params=params,
            )
        except httpx.TimeoutException as e:
            raise DripNetworkError(f"Request timed out: {path}", original_error=e) from e
        except httpx.RequestError as e:
            raise DripNetworkError(f"Network error: {e}", original_error=e) from e

        # Handle error responses
        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"error": response.text or "Unknown error"}

            raise create_api_error_from_response(response.status_code, body)

        # Parse successful response
        if response.status_code == 204:
            return {}

        try:
            result: dict[str, Any] = response.json()
            return result
        except Exception:
            return {}

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a GET request."""
        return self._request("GET", path, params=params)

    def _post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request."""
        return self._request("POST", path, json=json)

    def _put(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a PUT request."""
        return self._request("PUT", path, json=json)

    def _delete(self, path: str) -> dict[str, Any]:
        """Make a DELETE request."""
        return self._request("DELETE", path)

    # =========================================================================
    # Customer Management
    # =========================================================================

    def create_customer(
        self,
        onchain_address: str,
        external_customer_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Customer:
        """
        Create a new customer.

        Args:
            onchain_address: Customer's smart account address.
            external_customer_id: Your internal customer ID.
            metadata: Custom metadata.

        Returns:
            The created Customer object.
        """
        body: dict[str, Any] = {"onchainAddress": onchain_address}

        if external_customer_id:
            body["externalCustomerId"] = external_customer_id
        if metadata:
            body["metadata"] = metadata

        response = self._post("/customers", json=body)
        return Customer.model_validate(response)

    def get_customer(self, customer_id: str) -> Customer:
        """
        Get a customer by ID.

        Args:
            customer_id: The customer ID.

        Returns:
            The Customer object.
        """
        response = self._get(f"/customers/{customer_id}")
        return Customer.model_validate(response)

    def list_customers(
        self,
        status: CustomerStatus | None = None,
        limit: int = 100,
    ) -> ListCustomersResponse:
        """
        List customers with optional filtering.

        Args:
            status: Filter by status (ACTIVE, LOW_BALANCE, PAUSED).
            limit: Maximum number of results (1-100).

        Returns:
            List of customers with count.
        """
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status.value

        response = self._get("/customers", params=params)
        return ListCustomersResponse.model_validate(response)

    def get_balance(self, customer_id: str) -> BalanceResult:
        """
        Get a customer's current balance.

        Args:
            customer_id: The customer ID.

        Returns:
            Balance information including USDC and native token balances.
        """
        response = self._get(f"/customers/{customer_id}/balance")
        return BalanceResult.model_validate(response)

    # =========================================================================
    # Charging & Usage
    # =========================================================================

    def charge(
        self,
        customer_id: str,
        meter: str,
        quantity: float,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChargeResult:
        """
        Create a charge for usage.

        This is the primary billing method. It records usage and charges
        the customer's account.

        Args:
            customer_id: The customer ID.
            meter: Usage meter type (e.g., "api_calls", "tokens").
            quantity: Amount to charge.
            idempotency_key: Optional key to prevent duplicate charges.
            metadata: Optional metadata.

        Returns:
            ChargeResult with charge details and transaction hash.
        """
        body: dict[str, Any] = {
            "customerId": customer_id,
            "meter": meter,
            "quantity": quantity,
        }

        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
        if metadata:
            body["metadata"] = metadata

        response = self._post("/charges", json=body)
        return ChargeResult.model_validate(response)

    def get_charge(self, charge_id: str) -> Charge:
        """
        Get detailed charge information.

        Args:
            charge_id: The charge ID.

        Returns:
            Full Charge object with customer and usage event details.
        """
        response = self._get(f"/charges/{charge_id}")
        return Charge.model_validate(response)

    def list_charges(
        self,
        customer_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> ListChargesResponse:
        """
        List charges with optional filtering.

        Args:
            customer_id: Filter by customer.
            status: Filter by status.
            limit: Maximum results (1-100).

        Returns:
            List of charges with count.
        """
        params: dict[str, Any] = {"limit": limit}
        if customer_id:
            params["customerId"] = customer_id
        if status:
            params["status"] = status

        response = self._get("/charges", params=params)
        return ListChargesResponse.model_validate(response)

    def get_charge_status(self, charge_id: str) -> ChargeStatusResult:
        """
        Quick status check for a charge.

        Args:
            charge_id: The charge ID.

        Returns:
            Status and optional transaction hash.
        """
        response = self._get(f"/charges/{charge_id}/status")
        return ChargeStatusResult.model_validate(response)

    # =========================================================================
    # Checkout (Fiat On-Ramp)
    # =========================================================================

    def checkout(
        self,
        amount: int,
        return_url: str,
        customer_id: str | None = None,
        external_customer_id: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutResult:
        """
        Create a checkout session for customers to add funds.

        This is the primary method for getting money into Drip accounts.
        Supports ACH, debit card, and direct USDC.

        Args:
            amount: Amount in cents (5000 = $50.00).
            return_url: Redirect URL after successful payment.
            customer_id: Optional existing customer ID.
            external_customer_id: For new customers (your internal ID).
            cancel_url: Optional redirect URL on cancellation.
            metadata: Optional metadata.

        Returns:
            CheckoutResult with hosted checkout URL.
        """
        body: dict[str, Any] = {
            "amount": amount,
            "returnUrl": return_url,
        }

        if customer_id:
            body["customerId"] = customer_id
        if external_customer_id:
            body["externalCustomerId"] = external_customer_id
        if cancel_url:
            body["cancelUrl"] = cancel_url
        if metadata:
            body["metadata"] = metadata

        response = self._post("/checkout", json=body)
        return CheckoutResult.model_validate(response)

    # =========================================================================
    # Webhooks
    # =========================================================================

    def create_webhook(
        self,
        url: str,
        events: list[str],
        description: str | None = None,
    ) -> CreateWebhookResponse:
        """
        Create a webhook endpoint.

        IMPORTANT: The secret is returned only once - store it securely!

        Args:
            url: HTTPS endpoint URL.
            events: List of event types to subscribe to.
            description: Optional description.

        Returns:
            Webhook with secret (store the secret securely!).
        """
        body: dict[str, Any] = {
            "url": url,
            "events": events,
        }

        if description:
            body["description"] = description

        response = self._post("/webhooks", json=body)
        return CreateWebhookResponse.model_validate(response)

    def list_webhooks(self) -> ListWebhooksResponse:
        """
        List all webhooks with delivery statistics.

        Returns:
            List of webhooks with stats.
        """
        response = self._get("/webhooks")
        return ListWebhooksResponse.model_validate(response)

    def get_webhook(self, webhook_id: str) -> Webhook:
        """
        Get a specific webhook.

        Args:
            webhook_id: The webhook ID.

        Returns:
            Webhook details.
        """
        response = self._get(f"/webhooks/{webhook_id}")
        return Webhook.model_validate(response)

    def delete_webhook(self, webhook_id: str) -> DeleteWebhookResponse:
        """
        Delete a webhook.

        Args:
            webhook_id: The webhook ID.

        Returns:
            Deletion confirmation.
        """
        response = self._delete(f"/webhooks/{webhook_id}")
        return DeleteWebhookResponse.model_validate(response)

    def test_webhook(self, webhook_id: str) -> TestWebhookResponse:
        """
        Send a test event to a webhook.

        Args:
            webhook_id: The webhook ID.

        Returns:
            Test result with delivery ID.
        """
        response = self._post(f"/webhooks/{webhook_id}/test")
        return TestWebhookResponse.model_validate(response)

    def rotate_webhook_secret(self, webhook_id: str) -> RotateWebhookSecretResponse:
        """
        Generate a new webhook secret.

        Args:
            webhook_id: The webhook ID.

        Returns:
            New secret (store securely!).
        """
        response = self._post(f"/webhooks/{webhook_id}/rotate-secret")
        return RotateWebhookSecretResponse.model_validate(response)

    # =========================================================================
    # Workflows
    # =========================================================================

    def create_workflow(
        self,
        name: str,
        slug: str,
        product_surface: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Workflow:
        """
        Create a workflow definition for tracking agent runs.

        Args:
            name: Human-readable workflow name.
            slug: URL-safe identifier.
            product_surface: Type (RPC, WEBHOOK, AGENT, PIPELINE, CUSTOM).
            description: Optional description.
            metadata: Optional metadata.

        Returns:
            Created Workflow.
        """
        body: dict[str, Any] = {
            "name": name,
            "slug": slug,
        }

        if product_surface:
            body["productSurface"] = product_surface
        if description:
            body["description"] = description
        if metadata:
            body["metadata"] = metadata

        response = self._post("/workflows", json=body)
        return Workflow.model_validate(response)

    def list_workflows(self) -> ListWorkflowsResponse:
        """
        List all workflows.

        Returns:
            List of workflows with count.
        """
        response = self._get("/workflows")
        return ListWorkflowsResponse.model_validate(response)

    # =========================================================================
    # Agent Runs
    # =========================================================================

    def start_run(
        self,
        customer_id: str,
        workflow_id: str,
        external_run_id: str | None = None,
        correlation_id: str | None = None,
        parent_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunResult:
        """
        Start a new agent run.

        Args:
            customer_id: The customer ID.
            workflow_id: The workflow ID.
            external_run_id: Your internal run ID.
            correlation_id: For distributed tracing.
            parent_run_id: For nested runs.
            metadata: Optional metadata.

        Returns:
            RunResult with run ID and status.
        """
        body: dict[str, Any] = {
            "customerId": customer_id,
            "workflowId": workflow_id,
        }

        if external_run_id:
            body["externalRunId"] = external_run_id
        if correlation_id:
            body["correlationId"] = correlation_id
        if parent_run_id:
            body["parentRunId"] = parent_run_id
        if metadata:
            body["metadata"] = metadata

        response = self._post("/runs", json=body)
        return RunResult.model_validate(response)

    def end_run(
        self,
        run_id: str,
        status: str,
        error_message: str | None = None,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EndRunResult:
        """
        End an agent run.

        Args:
            run_id: The run ID.
            status: Final status (COMPLETED, FAILED, CANCELLED, TIMEOUT).
            error_message: Optional error message for failed runs.
            error_code: Optional error code.
            metadata: Optional metadata.

        Returns:
            EndRunResult with final status and totals.
        """
        body: dict[str, Any] = {"status": status}

        if error_message:
            body["errorMessage"] = error_message
        if error_code:
            body["errorCode"] = error_code
        if metadata:
            body["metadata"] = metadata

        response = self._post(f"/runs/{run_id}/end", json=body)
        return EndRunResult.model_validate(response)

    def emit_event(
        self,
        run_id: str,
        event_type: str,
        quantity: float | None = None,
        units: str | None = None,
        description: str | None = None,
        cost_units: float | None = None,
        cost_currency: str | None = None,
        correlation_id: str | None = None,
        parent_event_id: str | None = None,
        span_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EventResult:
        """
        Emit an event within a run.

        Args:
            run_id: The run ID.
            event_type: Event type (e.g., "agent.step", "tool.call").
            quantity: Optional quantity.
            units: Unit label (e.g., "tokens", "pages").
            description: Optional description.
            cost_units: Optional cost in units.
            cost_currency: Cost currency.
            correlation_id: For distributed tracing.
            parent_event_id: For nested events.
            span_id: OpenTelemetry span ID.
            idempotency_key: Prevent duplicate events.
            metadata: Optional metadata.

        Returns:
            EventResult with event ID and duplicate status.
        """
        body: dict[str, Any] = {
            "runId": run_id,
            "eventType": event_type,
        }

        if quantity is not None:
            body["quantity"] = quantity
        if units:
            body["units"] = units
        if description:
            body["description"] = description
        if cost_units is not None:
            body["costUnits"] = cost_units
        if cost_currency:
            body["costCurrency"] = cost_currency
        if correlation_id:
            body["correlationId"] = correlation_id
        if parent_event_id:
            body["parentEventId"] = parent_event_id
        if span_id:
            body["spanId"] = span_id
        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
        if metadata:
            body["metadata"] = metadata

        response = self._post("/events", json=body)
        return EventResult.model_validate(response)

    def emit_events_batch(
        self,
        events: list[dict[str, Any]],
    ) -> EmitEventsBatchResult:
        """
        Emit multiple events in one request.

        Args:
            events: List of event objects with runId, eventType, etc.

        Returns:
            Batch result with created count and duplicates.
        """
        response = self._post("/events/batch", json={"events": events})
        return EmitEventsBatchResult.model_validate(response)

    def get_run_timeline(self, run_id: str) -> RunTimeline:
        """
        Get the full timeline for a run.

        Args:
            run_id: The run ID.

        Returns:
            RunTimeline with events and computed totals.
        """
        response = self._get(f"/runs/{run_id}/timeline")
        return RunTimeline.model_validate(response)

    # =========================================================================
    # Simplified API: Record Run
    # =========================================================================

    def record_run(
        self,
        customer_id: str,
        workflow: str,
        events: list[dict[str, Any]],
        status: str,
        error_message: str | None = None,
        error_code: str | None = None,
        external_run_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RecordRunResult:
        """
        One-call simplified API for recording a complete agent run.

        This combines workflow creation (if needed), run creation,
        event emission, and run completion into a single call.

        Args:
            customer_id: The customer ID.
            workflow: Workflow ID or slug (auto-creates if slug).
            events: List of events with eventType, quantity, etc.
            status: Final status (COMPLETED, FAILED, CANCELLED, TIMEOUT).
            error_message: Optional error message.
            error_code: Optional error code.
            external_run_id: Your internal run ID.
            correlation_id: For distributed tracing.
            metadata: Optional metadata.

        Returns:
            RecordRunResult with run info and event stats.
        """
        body: dict[str, Any] = {
            "customerId": customer_id,
            "workflow": workflow,
            "events": events,
            "status": status,
        }

        if error_message:
            body["errorMessage"] = error_message
        if error_code:
            body["errorCode"] = error_code
        if external_run_id:
            body["externalRunId"] = external_run_id
        if correlation_id:
            body["correlationId"] = correlation_id
        if metadata:
            body["metadata"] = metadata

        response = self._post("/runs/record", json=body)
        return RecordRunResult.model_validate(response)

    # =========================================================================
    # Meters
    # =========================================================================

    def list_meters(self) -> ListMetersResponse:
        """
        List available usage meters from pricing plans.

        Returns:
            List of meters with pricing information.
        """
        response = self._get("/meters")
        return ListMetersResponse.model_validate(response)

    # =========================================================================
    # Static Utility Methods
    # =========================================================================

    @staticmethod
    def generate_idempotency_key(
        customer_id: str,
        step_name: str,
        run_id: str | None = None,
        sequence: int | None = None,
    ) -> str:
        """
        Generate a deterministic idempotency key.

        Ensures "one logical action = one event" even with retries.

        Args:
            customer_id: The customer ID.
            step_name: The name of the step/action.
            run_id: Optional run ID for scoping.
            sequence: Optional sequence number.

        Returns:
            Deterministic idempotency key.
        """
        return generate_idempotency_key(customer_id, step_name, run_id, sequence)

    @staticmethod
    def verify_webhook_signature(
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify a webhook signature.

        Uses HMAC-SHA256 with timing-safe comparison.

        Args:
            payload: Raw request body as string.
            signature: X-Drip-Signature header value.
            secret: Webhook secret.

        Returns:
            True if signature is valid.
        """
        return verify_webhook_signature(payload, signature, secret)

    # =========================================================================
    # StreamMeter Factory
    # =========================================================================

    def create_stream_meter(
        self,
        customer_id: str,
        meter: str,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        flush_threshold: float | None = None,
        on_add: Any = None,
        on_flush: Any = None,
    ) -> StreamMeter:
        """
        Create a StreamMeter for accumulating usage and charging once.

        Perfect for LLM token streaming where you want to:
        - Accumulate tokens locally (no API call per token)
        - Charge once at the end of the stream
        - Handle partial failures (charge for what was delivered)

        Args:
            customer_id: The Drip customer ID to charge.
            meter: The usage meter/type to record against.
            idempotency_key: Optional base key for idempotent charges.
            metadata: Optional metadata to attach to the charge.
            flush_threshold: Optional auto-flush when quantity exceeds this.
            on_add: Optional callback(quantity, total) on each add.
            on_flush: Optional callback(result) after each flush.

        Returns:
            A new StreamMeter instance.

        Example:
            >>> meter = client.create_stream_meter(
            ...     customer_id="cust_abc123",
            ...     meter="tokens",
            ... )
            >>>
            >>> for chunk in llm_stream:
            ...     meter.add_sync(chunk.tokens)
            >>>
            >>> result = meter.flush()
            >>> print(f"Charged {result.charge.amount_usdc} for {result.quantity} tokens")
        """
        options = StreamMeterOptions(
            customer_id=customer_id,
            meter=meter,
            idempotency_key=idempotency_key,
            metadata=metadata,
            flush_threshold=flush_threshold,
            on_add=on_add,
            on_flush=on_flush,
        )
        return StreamMeter(_charge_fn=self.charge, _options=options)


class AsyncDrip:
    """
    Async version of the Drip client.

    Provides the same API as Drip but with async/await support.

    Example:
        >>> from drip import AsyncDrip
        >>>
        >>> async with AsyncDrip(api_key="drip_sk_...") as client:
        ...     customer = await client.create_customer(
        ...         onchain_address="0x123..."
        ...     )
    """

    DEFAULT_BASE_URL = "https://api.drip.dev/v1"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """
        Initialize the async Drip client.

        Args:
            api_key: API key from Drip dashboard.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key or os.environ.get("DRIP_API_KEY")
        if not self._api_key:
            raise DripAuthenticationError(
                "API key is required. Pass it directly or set DRIP_API_KEY environment variable."
            )

        self._base_url = (
            base_url or os.environ.get("DRIP_API_URL") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self._timeout = timeout or self.DEFAULT_TIMEOUT

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "drip-sdk-python/1.0.0",
            },
        )

    async def __aenter__(self) -> AsyncDrip:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    @property
    def config(self) -> DripConfig:
        """Get the current configuration."""
        # api_key is guaranteed to be non-None after __init__
        assert self._api_key is not None
        return DripConfig(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )

    # =========================================================================
    # HTTP Request Helpers
    # =========================================================================

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an async HTTP request."""
        try:
            response = await self._client.request(
                method=method,
                url=path,
                json=json,
                params=params,
            )
        except httpx.TimeoutException as e:
            raise DripNetworkError(f"Request timed out: {path}", original_error=e) from e
        except httpx.RequestError as e:
            raise DripNetworkError(f"Network error: {e}", original_error=e) from e

        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"error": response.text or "Unknown error"}

            raise create_api_error_from_response(response.status_code, body)

        if response.status_code == 204:
            return {}

        try:
            result: dict[str, Any] = response.json()
            return result
        except Exception:
            return {}

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an async GET request."""
        return await self._request("GET", path, params=params)

    async def _post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an async POST request."""
        return await self._request("POST", path, json=json)

    async def _put(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an async PUT request."""
        return await self._request("PUT", path, json=json)

    async def _delete(self, path: str) -> dict[str, Any]:
        """Make an async DELETE request."""
        return await self._request("DELETE", path)

    # =========================================================================
    # Customer Management
    # =========================================================================

    async def create_customer(
        self,
        onchain_address: str,
        external_customer_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Customer:
        """Create a new customer."""
        body: dict[str, Any] = {"onchainAddress": onchain_address}

        if external_customer_id:
            body["externalCustomerId"] = external_customer_id
        if metadata:
            body["metadata"] = metadata

        response = await self._post("/customers", json=body)
        return Customer.model_validate(response)

    async def get_customer(self, customer_id: str) -> Customer:
        """Get a customer by ID."""
        response = await self._get(f"/customers/{customer_id}")
        return Customer.model_validate(response)

    async def list_customers(
        self,
        status: CustomerStatus | None = None,
        limit: int = 100,
    ) -> ListCustomersResponse:
        """List customers with optional filtering."""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status.value

        response = await self._get("/customers", params=params)
        return ListCustomersResponse.model_validate(response)

    async def get_balance(self, customer_id: str) -> BalanceResult:
        """Get a customer's current balance."""
        response = await self._get(f"/customers/{customer_id}/balance")
        return BalanceResult.model_validate(response)

    # =========================================================================
    # Charging & Usage
    # =========================================================================

    async def charge(
        self,
        customer_id: str,
        meter: str,
        quantity: float,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChargeResult:
        """Create a charge for usage."""
        body: dict[str, Any] = {
            "customerId": customer_id,
            "meter": meter,
            "quantity": quantity,
        }

        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
        if metadata:
            body["metadata"] = metadata

        response = await self._post("/charges", json=body)
        return ChargeResult.model_validate(response)

    async def get_charge(self, charge_id: str) -> Charge:
        """Get detailed charge information."""
        response = await self._get(f"/charges/{charge_id}")
        return Charge.model_validate(response)

    async def list_charges(
        self,
        customer_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> ListChargesResponse:
        """List charges with optional filtering."""
        params: dict[str, Any] = {"limit": limit}
        if customer_id:
            params["customerId"] = customer_id
        if status:
            params["status"] = status

        response = await self._get("/charges", params=params)
        return ListChargesResponse.model_validate(response)

    async def get_charge_status(self, charge_id: str) -> ChargeStatusResult:
        """Quick status check for a charge."""
        response = await self._get(f"/charges/{charge_id}/status")
        return ChargeStatusResult.model_validate(response)

    # =========================================================================
    # Checkout
    # =========================================================================

    async def checkout(
        self,
        amount: int,
        return_url: str,
        customer_id: str | None = None,
        external_customer_id: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutResult:
        """Create a checkout session."""
        body: dict[str, Any] = {
            "amount": amount,
            "returnUrl": return_url,
        }

        if customer_id:
            body["customerId"] = customer_id
        if external_customer_id:
            body["externalCustomerId"] = external_customer_id
        if cancel_url:
            body["cancelUrl"] = cancel_url
        if metadata:
            body["metadata"] = metadata

        response = await self._post("/checkout", json=body)
        return CheckoutResult.model_validate(response)

    # =========================================================================
    # Webhooks
    # =========================================================================

    async def create_webhook(
        self,
        url: str,
        events: list[str],
        description: str | None = None,
    ) -> CreateWebhookResponse:
        """Create a webhook endpoint."""
        body: dict[str, Any] = {
            "url": url,
            "events": events,
        }

        if description:
            body["description"] = description

        response = await self._post("/webhooks", json=body)
        return CreateWebhookResponse.model_validate(response)

    async def list_webhooks(self) -> ListWebhooksResponse:
        """List all webhooks."""
        response = await self._get("/webhooks")
        return ListWebhooksResponse.model_validate(response)

    async def get_webhook(self, webhook_id: str) -> Webhook:
        """Get a specific webhook."""
        response = await self._get(f"/webhooks/{webhook_id}")
        return Webhook.model_validate(response)

    async def delete_webhook(self, webhook_id: str) -> DeleteWebhookResponse:
        """Delete a webhook."""
        response = await self._delete(f"/webhooks/{webhook_id}")
        return DeleteWebhookResponse.model_validate(response)

    async def test_webhook(self, webhook_id: str) -> TestWebhookResponse:
        """Send a test event to a webhook."""
        response = await self._post(f"/webhooks/{webhook_id}/test")
        return TestWebhookResponse.model_validate(response)

    async def rotate_webhook_secret(
        self, webhook_id: str
    ) -> RotateWebhookSecretResponse:
        """Generate a new webhook secret."""
        response = await self._post(f"/webhooks/{webhook_id}/rotate-secret")
        return RotateWebhookSecretResponse.model_validate(response)

    # =========================================================================
    # Workflows
    # =========================================================================

    async def create_workflow(
        self,
        name: str,
        slug: str,
        product_surface: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Workflow:
        """Create a workflow definition."""
        body: dict[str, Any] = {
            "name": name,
            "slug": slug,
        }

        if product_surface:
            body["productSurface"] = product_surface
        if description:
            body["description"] = description
        if metadata:
            body["metadata"] = metadata

        response = await self._post("/workflows", json=body)
        return Workflow.model_validate(response)

    async def list_workflows(self) -> ListWorkflowsResponse:
        """List all workflows."""
        response = await self._get("/workflows")
        return ListWorkflowsResponse.model_validate(response)

    # =========================================================================
    # Agent Runs
    # =========================================================================

    async def start_run(
        self,
        customer_id: str,
        workflow_id: str,
        external_run_id: str | None = None,
        correlation_id: str | None = None,
        parent_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunResult:
        """Start a new agent run."""
        body: dict[str, Any] = {
            "customerId": customer_id,
            "workflowId": workflow_id,
        }

        if external_run_id:
            body["externalRunId"] = external_run_id
        if correlation_id:
            body["correlationId"] = correlation_id
        if parent_run_id:
            body["parentRunId"] = parent_run_id
        if metadata:
            body["metadata"] = metadata

        response = await self._post("/runs", json=body)
        return RunResult.model_validate(response)

    async def end_run(
        self,
        run_id: str,
        status: str,
        error_message: str | None = None,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EndRunResult:
        """End an agent run."""
        body: dict[str, Any] = {"status": status}

        if error_message:
            body["errorMessage"] = error_message
        if error_code:
            body["errorCode"] = error_code
        if metadata:
            body["metadata"] = metadata

        response = await self._post(f"/runs/{run_id}/end", json=body)
        return EndRunResult.model_validate(response)

    async def emit_event(
        self,
        run_id: str,
        event_type: str,
        quantity: float | None = None,
        units: str | None = None,
        description: str | None = None,
        cost_units: float | None = None,
        cost_currency: str | None = None,
        correlation_id: str | None = None,
        parent_event_id: str | None = None,
        span_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EventResult:
        """Emit an event within a run."""
        body: dict[str, Any] = {
            "runId": run_id,
            "eventType": event_type,
        }

        if quantity is not None:
            body["quantity"] = quantity
        if units:
            body["units"] = units
        if description:
            body["description"] = description
        if cost_units is not None:
            body["costUnits"] = cost_units
        if cost_currency:
            body["costCurrency"] = cost_currency
        if correlation_id:
            body["correlationId"] = correlation_id
        if parent_event_id:
            body["parentEventId"] = parent_event_id
        if span_id:
            body["spanId"] = span_id
        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
        if metadata:
            body["metadata"] = metadata

        response = await self._post("/events", json=body)
        return EventResult.model_validate(response)

    async def emit_events_batch(
        self,
        events: list[dict[str, Any]],
    ) -> EmitEventsBatchResult:
        """Emit multiple events in one request."""
        response = await self._post("/events/batch", json={"events": events})
        return EmitEventsBatchResult.model_validate(response)

    async def get_run_timeline(self, run_id: str) -> RunTimeline:
        """Get the full timeline for a run."""
        response = await self._get(f"/runs/{run_id}/timeline")
        return RunTimeline.model_validate(response)

    # =========================================================================
    # Simplified API
    # =========================================================================

    async def record_run(
        self,
        customer_id: str,
        workflow: str,
        events: list[dict[str, Any]],
        status: str,
        error_message: str | None = None,
        error_code: str | None = None,
        external_run_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RecordRunResult:
        """One-call simplified API for recording a complete agent run."""
        body: dict[str, Any] = {
            "customerId": customer_id,
            "workflow": workflow,
            "events": events,
            "status": status,
        }

        if error_message:
            body["errorMessage"] = error_message
        if error_code:
            body["errorCode"] = error_code
        if external_run_id:
            body["externalRunId"] = external_run_id
        if correlation_id:
            body["correlationId"] = correlation_id
        if metadata:
            body["metadata"] = metadata

        response = await self._post("/runs/record", json=body)
        return RecordRunResult.model_validate(response)

    # =========================================================================
    # Meters
    # =========================================================================

    async def list_meters(self) -> ListMetersResponse:
        """List available usage meters."""
        response = await self._get("/meters")
        return ListMetersResponse.model_validate(response)

    # =========================================================================
    # Static Utility Methods
    # =========================================================================

    @staticmethod
    def generate_idempotency_key(
        customer_id: str,
        step_name: str,
        run_id: str | None = None,
        sequence: int | None = None,
    ) -> str:
        """Generate a deterministic idempotency key."""
        return generate_idempotency_key(customer_id, step_name, run_id, sequence)

    @staticmethod
    def verify_webhook_signature(
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify a webhook signature."""
        return verify_webhook_signature(payload, signature, secret)

    # =========================================================================
    # StreamMeter Factory
    # =========================================================================

    def create_stream_meter(
        self,
        customer_id: str,
        meter: str,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        flush_threshold: float | None = None,
        on_add: Any = None,
        on_flush: Any = None,
    ) -> StreamMeter:
        """
        Create a StreamMeter for accumulating usage and charging once (async).

        Perfect for LLM token streaming where you want to:
        - Accumulate tokens locally (no API call per token)
        - Charge once at the end of the stream
        - Handle partial failures (charge for what was delivered)

        Args:
            customer_id: The Drip customer ID to charge.
            meter: The usage meter/type to record against.
            idempotency_key: Optional base key for idempotent charges.
            metadata: Optional metadata to attach to the charge.
            flush_threshold: Optional auto-flush when quantity exceeds this.
            on_add: Optional callback(quantity, total) on each add.
            on_flush: Optional callback(result) after each flush.

        Returns:
            A new StreamMeter instance.

        Example:
            >>> async with AsyncDrip(api_key="...") as client:
            ...     meter = client.create_stream_meter(
            ...         customer_id="cust_abc123",
            ...         meter="tokens",
            ...     )
            ...
            ...     async for chunk in llm_stream:
            ...         await meter.add(chunk.tokens)  # May auto-flush
            ...
            ...     result = await meter.flush_async()
            ...     print(f"Charged {result.charge.amount_usdc}")
        """
        options = StreamMeterOptions(
            customer_id=customer_id,
            meter=meter,
            idempotency_key=idempotency_key,
            metadata=metadata,
            flush_threshold=flush_threshold,
            on_add=on_add,
            on_flush=on_flush,
        )
        return StreamMeter(_charge_fn=self.charge, _options=options)
