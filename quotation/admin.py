from django.contrib import admin
from .models import (
    CompanyDetails,
    PaymentPlan,
    Quotation,
    QuotationItem,
    QuotationSection,
)

admin.site.register(Quotation)
admin.site.register(QuotationSection)
admin.site.register(QuotationItem)
admin.site.register(PaymentPlan)
admin.site.register(CompanyDetails)
