from django import forms


class AddDomainForm(forms.Form):
    host = forms.CharField(max_length=253)
    dns_contact_email = forms.EmailField(required=False)
