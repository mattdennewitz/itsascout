from django import forms
from publishers.models import Publisher


class PublisherForm(forms.ModelForm):
    """Form for creating and updating publishers."""

    class Meta:
        model = Publisher
        fields = ['name', 'url']

    def clean_url(self):
        """Validate URL starts with http:// or https://."""
        url = self.cleaned_data.get('url')
        if url and not (url.startswith('http://') or url.startswith('https://')):
            raise forms.ValidationError('URL must start with http:// or https://')
        return url


class BulkUploadForm(forms.Form):
    """Form for bulk CSV upload of publisher URLs."""

    csv_file = forms.FileField(required=True)

    def clean_csv_file(self):
        """Validate CSV file extension and size."""
        csv_file = self.cleaned_data.get('csv_file')

        if csv_file:
            # Check file extension
            if not csv_file.name.endswith('.csv'):
                raise forms.ValidationError('File must be a CSV file (.csv extension)')

            # Check file size (5MB limit)
            if csv_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 5MB')

        return csv_file
