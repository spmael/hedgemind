# Generated manually for updating issuer_code constraints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reference_data", "0011_alter_issuer_lei"),
    ]

    operations = [
        # Remove the per-organization unique constraint
        migrations.RemoveConstraint(
            model_name="issuer",
            name="unique_issuer_per_org",
        ),
        # Add unique=True to issuer_code field (globally unique)
        migrations.AlterField(
            model_name="issuer",
            name="issuer_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    "Stable identifier code following format [REGION]-[TYPE]-[IDENTIFIER] "
                    "(e.g., CM-SOV-GOVT, GA-BNK-BANQUEDEGAB). "
                    "Auto-generated if not provided. Globally unique."
                ),
                max_length=50,
                null=True,
                unique=True,
                verbose_name="Issuer Code",
            ),
        ),
    ]
