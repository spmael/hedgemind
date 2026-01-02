# Generated manually for adding issuer_code and lei fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reference_data", "0006_instrument_amortization_method_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="issuer",
            name="issuer_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Stable identifier code for cross-org consistency (globally unique).",
                max_length=50,
                null=True,
                unique=True,
                verbose_name="Issuer Code",
            ),
        ),
        migrations.AddField(
            model_name="issuer",
            name="lei",
            field=models.CharField(
                blank=True,
                help_text="Legal Entity Identifier (20-character code).",
                max_length=30,
                null=True,
                verbose_name="LEI",
            ),
        ),
        migrations.AddIndex(
            model_name="issuer",
            index=models.Index(
                fields=["issuer_code"],
                name="reference_d_issuer__code_idx",
            ),
        ),
    ]

