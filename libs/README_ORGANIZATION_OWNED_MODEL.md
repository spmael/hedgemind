# OrganizationOwnedModel Usage Guide

## Overview

The `OrganizationOwnedModel` mixin provides automatic organization scoping for Django models. It ensures that all queries are automatically filtered by the current organization context, preventing accidental data leaks across organizations.

## Features

- **Automatic organization scoping**: All queries (`all()`, `filter()`, `get()`, etc.) automatically filter by current org
- **Auto-set organization on save**: Automatically sets `organization_id` from thread-local context
- **Prevents data leaks**: Cannot accidentally query across organizations
- **Type-safe**: Clear which models are organization-scoped

## Usage

### Basic Example

```python
from libs.models import OrganizationOwnedModel
from django.db import models

class Portfolio(OrganizationOwnedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Portfolio"
        verbose_name_plural = "Portfolios"
```

### What Gets Added

When you inherit from `OrganizationOwnedModel`, you automatically get:

1. **`organization` ForeignKey**: Automatically added to your model
2. **Custom Manager**: `objects` manager that auto-filters by org
3. **Auto-save behavior**: Sets `organization_id` from context on save

### Querying

```python
# All queries are automatically scoped to current organization
portfolios = Portfolio.objects.all()  # Only returns portfolios for current org
portfolio = Portfolio.objects.get(name="My Portfolio")  # Only searches in current org
portfolio = Portfolio.objects.filter(name__icontains="test")  # Auto-filtered

# Create automatically sets organization_id from context
portfolio = Portfolio.objects.create(name="New Portfolio")  # organization_id set automatically
```

### Manual Organization Override

If you need to explicitly set the organization:

```python
from libs.tenant_context import organization_context

# Option 1: Set in context before creating
with organization_context(org_id=123):
    portfolio = Portfolio.objects.create(name="Portfolio")

# Option 2: Set explicitly
portfolio = Portfolio(name="Portfolio")
portfolio.organization_id = 123
portfolio.save()
```

### Accessing All Organizations (Admin/System Use)

If you need to access objects across all organizations (e.g., in admin or system tasks), you can use the raw manager:

```python
# This bypasses organization filtering
all_portfolios = Portfolio._base_manager.all()  # All portfolios across all orgs
```

**Warning**: Only use `_base_manager` in admin interfaces or system-level code. Never use it in user-facing views.

## Migration

When adding `OrganizationOwnedModel` to an existing model:

1. Create a migration to add the `organization` ForeignKey
2. Set `null=True` initially if you have existing data
3. Populate `organization_id` for existing records
4. Set `null=False` in a follow-up migration

Example migration:

```python
# 0002_add_organization_to_portfolio.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('portfolios', '0001_initial'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='portfolio',
            name='organization',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='portfolio_set',
                to='organizations.organization'
            ),
        ),
        # Populate organization_id for existing records
        migrations.RunPython(populate_organization_ids),
        # Make it required
        migrations.AlterField(
            model_name='portfolio',
            name='organization',
            field=models.ForeignKey(
                null=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='portfolio_set',
                to='organizations.organization'
            ),
        ),
    ]
```

## Best Practices

1. **Always use OrganizationOwnedModel** for models that belong to an organization
2. **Never bypass the manager** in user-facing code
3. **Set organization context** in Celery tasks explicitly (don't rely on middleware)
4. **Test organization isolation** - ensure queries don't leak across orgs

## Testing

```python
from libs.tenant_context import organization_context
from tests.factories import OrganizationFactory

def test_portfolio_isolation():
    org1 = OrganizationFactory()
    org2 = OrganizationFactory()
    
    with organization_context(org1.id):
        portfolio1 = Portfolio.objects.create(name="Portfolio 1")
    
    with organization_context(org2.id):
        portfolio2 = Portfolio.objects.create(name="Portfolio 2")
    
    # Verify isolation
    with organization_context(org1.id):
        assert Portfolio.objects.count() == 1
        assert portfolio1 in Portfolio.objects.all()
        assert portfolio2 not in Portfolio.objects.all()
```

