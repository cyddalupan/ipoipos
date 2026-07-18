"""Business logic for CASSEY POS."""

from decimal import Decimal, ROUND_HALF_UP
import json
import logging
import os
import urllib.request
import urllib.error

from django.db import transaction as db_transaction
from .models import Item, Transaction, TransactionItem, DiscountType, Patient, Queue

logger = logging.getLogger(__name__)


class DeepSeekService:
    """
    Service for interacting with the DeepSeek LLM API.
    Uses the OpenAI-compatible chat completions endpoint.

    Configurable via settings or environment variables:
    - DEEPSEEK_API_KEY (env) or settings.DEEPSEEK_API_KEY
    - DEEPSEEK_API_URL (env) or settings.DEEPSEEK_API_URL (default: https://api.deepseek.com/v1/chat/completions)
    - DEEPSEEK_MODEL (env) or settings.DEEPSEEK_MODEL (default: deepseek-chat)
    """

    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.api_url = os.environ.get(
            "DEEPSEEK_API_URL",
            "https://api.deepseek.com/v1/chat/completions"
        )
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    def chat(self, messages, max_tokens=500, temperature=0.7):
        """
        Send a chat completion request to DeepSeek API.

        Args:
            messages: List of dicts with 'role' and 'content' keys.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature (0.0-2.0).

        Returns:
            Response text string, or empty string on failure.
        """
        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not configured — returning empty response")
            return ""

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
        except urllib.error.HTTPError as e:
            logger.error(f"DeepSeek API HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}")
            return ""
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            logger.error(f"DeepSeek API error: {e}")
            return ""


class CheckoutEngine:
    """Processes a POS checkout cart with optional discounts."""

    TABLE_MIN = 1
    TABLE_MAX = 20

    VALID_ORDER_TYPES = {"DINE_IN", "TAKE_OUT"}

    def __init__(self, cart_data, discount_id=None, payment_method="CASH",
                 ref_num=None, total_diners=1, special_count=0,
                 table_number=None, order_type="DINE_IN",
                 vat_inclusive=True, manual_discount_pct=None):
        self.cart_data = cart_data
        self.discount_id = discount_id
        self.payment_method = payment_method
        self.ref_num = ref_num
        self.total_diners = total_diners
        self.special_count = special_count
        self.table_number = table_number
        self.order_type = order_type
        self.vat_inclusive = vat_inclusive
        self.manual_discount_pct = manual_discount_pct

        self.subtotal = Decimal("0.00")
        self.discount_amount = Decimal("0.00")
        self.vat_exempt_sales = Decimal("0.00")
        self.vat_amount = Decimal("0.00")
        self.grand_total = Decimal("0.00")

    def _compute_vat(self, vatable_amount):
        """Compute VAT breakdown for a vatable amount if vat_inclusive, else zero."""
        if not self.vat_inclusive:
            return Decimal("0.00"), Decimal("0.00")
        vat_exclusive = (vatable_amount / Decimal("1.12")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        vat_amount = vatable_amount - vat_exclusive
        return vat_exclusive, vat_amount

    def _validate_manual_discount(self):
        """Validate manual_discount_pct is in range 0-100."""
        if self.manual_discount_pct is not None:
            pct = Decimal(str(self.manual_discount_pct))
            if pct < Decimal("0") or pct > Decimal("100"):
                raise ValueError(
                    f"manual_discount_pct must be between 0 and 100, got {pct}"
                )

    def _apply_manual_discount(self):
        """Apply manual percentage discount to subtotal. Returns discount_amount."""
        if self.manual_discount_pct is not None:
            pct = Decimal(str(self.manual_discount_pct))
            amount = (self.subtotal * (pct / Decimal("100.00"))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)
            return amount
        return Decimal("0.00")

    def calculate_totals(self, discount_obj):
        for entry in self.cart_data:
            item = Item.objects.get(id=entry["item_id"])
            self.subtotal += item.selling_price * Decimal(entry["qty"])

        # Validate and apply manual discount first (reduces subtotal before VAT)
        self._validate_manual_discount()
        manual_discount = self._apply_manual_discount()
        discounted_subtotal = self.subtotal - manual_discount

        if discount_obj and discount_obj.is_active:
            if discount_obj.kind == "PERCENTAGE":
                self.discount_amount = (self.subtotal * (discount_obj.value / Decimal("100.00"))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                vtable_balance = discounted_subtotal - self.discount_amount
                self.vat_exclusive_sales, self.vat_amount = self._compute_vat(vtable_balance)
                self.grand_total = vtable_balance

            elif discount_obj.kind == "FIXED":
                self.discount_amount = discount_obj.value
                vtable_balance = max(Decimal("0.00"), discounted_subtotal - self.discount_amount)
                self.vat_exclusive_sales, self.vat_amount = self._compute_vat(vtable_balance)
                self.grand_total = vtable_balance

            elif discount_obj.kind == "PH_SPECIAL":
                gross_share = (discounted_subtotal / Decimal(self.total_diners)) * Decimal(self.special_count)
                if self.vat_inclusive:
                    vat_component_in_share = (gross_share - (gross_share / Decimal("1.12"))).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
                    vat_component_in_share = Decimal("0.00")
                exempt_base = (gross_share / Decimal("1.12")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                law_discount = (exempt_base * Decimal("0.20")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)

                self.discount_amount = law_discount
                self.grand_total = (discounted_subtotal - vat_component_in_share - law_discount).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                self.vat_exclusive_sales, self.vat_amount = self._compute_vat(self.grand_total)
        else:
            # No preset discount — use manual discount if set
            self.discount_amount = manual_discount
            self.vat_exclusive_sales, self.vat_amount = self._compute_vat(discounted_subtotal)
            self.grand_total = discounted_subtotal

    def process(self):
        discount_obj = DiscountType.objects.get(id=self.discount_id) if self.discount_id else None

        if self.table_number is not None:
            if not (self.TABLE_MIN <= self.table_number <= self.TABLE_MAX):
                raise ValueError(
                    f"Table number must be between {self.TABLE_MIN} and {self.TABLE_MAX}, "
                    f"got {self.table_number}"
                )

        if self.order_type not in self.VALID_ORDER_TYPES:
            raise ValueError(
                f"Invalid order_type '{self.order_type}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_ORDER_TYPES))}"
            )

        with db_transaction.atomic():
            self.calculate_totals(discount_obj)

            txn = Transaction.objects.create(
                subtotal=self.subtotal,
                discount_applied=discount_obj,
                discount_amount=self.discount_amount,
                vat_exclusive_sales=self.vat_exclusive_sales,
                vat_amount=self.vat_amount,
                grand_total=self.grand_total,
                payment_method=self.payment_method,
                reference_number=self.ref_num,
                total_diners=self.total_diners,
                special_cardholders_count=self.special_count,
                table_number=self.table_number,
                order_type=self.order_type,
                vat_inclusive=self.vat_inclusive,
                manual_discount_pct=self.manual_discount_pct
            )

            for entry in self.cart_data:
                item = Item.objects.select_for_update().get(id=entry["item_id"])
                if item.stock_qty < entry["qty"]:
                    raise ValueError(f"Insufficient stock for product: {item.name}")

                TransactionItem.objects.create(
                    transaction=txn,
                    item=item,
                    quantity=entry["qty"],
                    unit_price=item.selling_price,
                )
                item.stock_qty -= entry["qty"]
                item.save()

            return txn


class MessengerWebhookService:
    """
    Builds LLM context/prompts with patient clinic remarks injected.
    Remarks are used to inform the LLM — not revealed verbatim to the patient.

    Supports Smart Unregistered Chat:
    - Pre-registration: PSID not linked to any patient → clinic info prompt
    - In-queue: patient has active (waiting) queue entry → existing queue prompt
    - Post-queue: all queue entries served/cancelled/skipped → last queue + clinic info
    """

    SYSTEM_PROMPT_TEMPLATE = (
        "You are a helpful clinic assistant for Ipo-Ipo Clinic. "
        "You answer questions from patients based on their medical records and clinic remarks. "
        "When a patient asks about clinic notes or remarks, explain the information in a natural, helpful way. "
        "Do NOT reveal raw remark text verbatim unless the patient directly asks for the exact text. "
        "Keep answers concise, empathetic, and focused on helping the patient understand.\n"
    )
    REMARK_CONTEXT_TEMPLATE = (
        "\nClinic remark for {name}: {remarks}\n"
        "Use this information to answer the patient's questions naturally.\n"
    )

    # ----- Smart Unregistered Chat: Clinic Info Constants ----- #

    CLINIC_INFO = (
        "\n=== Ipo-Ipo Clinic Information ===\n"
        "Clinic Name: Ipo-Ipo Clinic\n"
        "Address: 123 Health Street, Barangay San Antonio, Quezon City, Philippines\n"
        "Operating Hours: Monday to Friday 8:00 AM - 5:00 PM, Saturday 8:00 AM - 12:00 PM\n"
        "Contact Number: (02) 8123-4567\n"
        "Email: info@ipoipoclinic.com\n"
        "Services Offered: General Check-up, TB Screening, Laboratory Tests, Vaccinations, "
        "X-Ray, Dental Check-up, Optical Consultation\n"
        "Walk-ins are welcome. No appointment needed for basic consultations.\n"
        "=============================="
    )

    PREREGISTRATION_SYSTEM_PROMPT = (
        "You are a helpful clinic assistant for Ipo-Ipo Clinic. "
        "A potential new patient is asking questions via Facebook Messenger. "
        "They have not yet registered or visited the clinic. "
        "Provide friendly, informative answers about clinic services, hours, location, "
        "and any general questions about the clinic. "
        "Encourage them to visit the clinic or register for an appointment. "
        "Keep answers concise, warm, and helpful.\n"
    )

    POSTQUEUE_SYSTEM_PROMPT = (
        "You are a helpful clinic assistant for Ipo-Ipo Clinic. "
        "You are speaking with a patient who has already been seen at the clinic. "
        "Answer questions about their recent visit, lab results, follow-up instructions, "
        "or any general clinic information. "
        "When a patient asks about clinic notes or remarks, explain the information "
        "in a natural, helpful way. Do NOT reveal raw remark text verbatim unless "
        "the patient directly asks for the exact text. "
        "Keep answers concise, empathetic, and focused on helping the patient understand.\n"
    )

    POSTQUEUE_CONTEXT_TEMPLATE = (
        "\n--- Patient Information ---\n"
        "Patient Name: {name}\n"
        "Last queue entry: {last_queue_entry}\n"
        "\nClinic remark for {name}: {remarks}\n"
        "Use this information to answer the patient's questions naturally.\n"
    )

    def __init__(self):
        self.deepseek = DeepSeekService()

    # ----- State Classification ----- #

    def classify_psid(self, psid):
        """
        Classify a Facebook PSID into one of three states:
        - 'preregistration': PSID not linked to any Patient
        - 'inqueue': Patient has at least one active (waiting) Queue entry
        - 'postqueue': Patient exists but has no active Queue entries
        """
        try:
            patient = Patient.objects.get(fb_psid=psid)
        except Patient.DoesNotExist:
            return "preregistration"

        active_entries = Queue.objects.filter(
            patient=patient, status="waiting"
        )
        if active_entries.exists():
            return "inqueue"

        return "postqueue"

    # ----- Prompt Builders ----- #

    def build_llm_context(self, patient):
        """
        Build LLM context string with patient clinic remarks.
        Returns empty string if patient is None or has no remarks.
        """
        if patient is None:
            return ""
        if not patient.remarks:
            return ""
        return self.REMARK_CONTEXT_TEMPLATE.format(
            name=patient.name,
            remarks=patient.remarks,
        )

    def build_system_prompt(self, patient):
        """
        Build the full system prompt with or without remark context.
        Used for in-queue patients (existing behavior).
        """
        prompt = self.SYSTEM_PROMPT_TEMPLATE
        context = self.build_llm_context(patient)
        if context:
            prompt += context
        return prompt

    def build_preregistration_prompt(self):
        """
        Build system prompt for pre-registration (unlinked PSID) users.
        Includes clinic info but no patient-specific data.
        """
        return self.PREREGISTRATION_SYSTEM_PROMPT + "\n" + self.CLINIC_INFO

    def build_postqueue_prompt(self, patient):
        """
        Build system prompt for post-queue patients.
        Includes last queue entry info, clinic remarks, and clinic general info.
        """
        last_entry = (
            Queue.objects.filter(patient=patient)
            .order_by("-created_at")
            .first()
        )

        last_queue_info = "No previous queue entries found."
        if last_entry:
            last_queue_info = (
                f"Status: {last_entry.status}, "
                f"Service: {last_entry.service or 'N/A'}, "
                f"Area: {last_entry.service_area or 'N/A'}"
            )

        prompt = self.POSTQUEUE_SYSTEM_PROMPT

        context = self.POSTQUEUE_CONTEXT_TEMPLATE.format(
            name=patient.name,
            last_queue_entry=last_queue_info,
            remarks=patient.remarks or "No remarks on file.",
        )
        prompt += context
        prompt += "\n" + self.CLINIC_INFO

        return prompt

    # ----- Orchestration ----- #

    def get_response_for_psid(self, psid, user_message):
        """
        Get an LLM response for a user message based on the PSID's state.

        State routing:
        - preregistration → clinic info prompt (no patient data)
        - inqueue → existing queue-aware prompt
        - postqueue → last queue info + clinic info
        """
        state = self.classify_psid(psid)

        if state == "preregistration":
            system_prompt = self.build_preregistration_prompt()
        elif state == "inqueue":
            patient = Patient.objects.get(fb_psid=psid)
            system_prompt = self.build_system_prompt(patient)
        else:
            patient = Patient.objects.get(fb_psid=psid)
            system_prompt = self.build_postqueue_prompt(patient)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        return self.deepseek.chat(messages)
