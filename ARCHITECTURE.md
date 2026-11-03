# Dealership Desk Architecture

## Layers

```text
Browser presentation
  Django template shell + static JavaScript modules
  app.js coordinates pages; core/api.js handles HTTP; core/format.js formats values
  pages/documents.js owns itemized sale and purchase entry

HTTP interface
  dealerships/interfaces/api/
  serializers validate and translate JSON; views enforce tenant scope and expose actions;
  auth.py handles account sessions/tokens; reports.py exposes read-only summaries

Application use cases
  dealerships/application/
  sales, purchasing, inventory, payments, and business setup
  Each posted operation is atomic and records its ledger effects

Domain and persistence
  dealerships/models.py
  Tenant-owned records, constraints, document history, and stock/payment ledgers
```

## Dependency rules

- Models do not depend on HTTP serializers, views, or browser code.
- Application use cases receive model instances and explicit input values; they do not read request objects.
- API views authenticate the caller, resolve an active `BusinessUser` membership, and scope every query to that business.
- Serializers validate external values and delegate multi-record operations to application use cases.
- Browser pages use the API and do not contain inventory or balance calculation rules.

## Operational invariants

- A dealership is the tenant boundary. Related business, location, product, contact, payment, and document IDs must belong to the same tenant.
- Posted stock changes are append-only `StockMovement` rows. A sale, receipt, transfer, or return and its ledger entries commit in one database transaction.
- Payment records are independent from invoices. `PaymentAllocation` links a payment to a sale or purchase and prevents allocating more than the remaining payment or document balance.
- Returns are separate documents. They cannot exceed the remaining quantity on the source line; supplier returns also cannot make stock negative.
- Posted documents and ledgers are corrected with a compensating operation, not by editing their history.

## Local development

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver
```

Open `/` for the dealership workspace and `/admin/` for Django administration. API endpoints are under `/api/`; signup creates an owner, dealership, and default location.
