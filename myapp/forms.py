from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from location_field.forms.plain import PlainLocationField
from .models import Profile, Product, Comment, StarsFeedback, Profile, Message

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required.')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name')

    def save(self, commit=True):
        user = super(SignUpForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


        
class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)  

class SearchForm(forms.Form):
    query = forms.CharField(max_length=100, label='')

class ProductForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('electronic', 'Electronic'),
        ('fashion', 'Fashion'),
        ('home_appliance', 'Home Appliance'),
        ('books', 'Books'),
        ('toys', 'Toys'),
        ('beauty', 'Beauty'),
        ('sports', 'Sports'),
        ('outdoor', 'Outdoor'),
        ('automotive', 'Automotive'),
        ('grocery', 'Grocery'),
        ('health', 'Health'),
        ('furniture', 'Furniture'),
        ('jewelry', 'Jewelry'),
        ('stationery', 'Stationery'),
        ('tools', 'Tools'),
        ('food', 'Food'),
    ]

    category = forms.ChoiceField(choices=CATEGORY_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))


    class Meta:
        model = Product
        fields = ['title', 'description', 'price', 'image', 'video', 'category']  


class StarsFeedbackForm(forms.ModelForm):
    STARS_CHOICES = [
        (1, '⭐'),
        (2, '⭐⭐'),
        (3, '⭐⭐⭐'),
        (4, '⭐⭐⭐⭐'),
        (5, '⭐⭐⭐⭐⭐'),
    ]
    stars = forms.ChoiceField(choices=STARS_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = StarsFeedback
        fields = ('stars',)

    def __init__(self, *args, product_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        for choice in self.STARS_CHOICES:
            self.fields[f'stars_{choice[0]}'] = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
                'class': 'star-picker-item btn-sm',
                'type': 'button',
                'data-stars': choice[1],
            }))

    def save(self, commit=True, author=None, product=None):
        stars_feedback = super().save(commit=False)
        stars_feedback.author = author
        stars_feedback.product = product
        if commit:
            stars_feedback.save()
        return stars_feedback     

class CommentForm(forms.ModelForm):
    comment = forms.CharField(
        label='',
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': '...', 'rows': '1'}),
    )

    class Meta:
        model = Comment
        fields = ['comment']      

class ProfileUpdateForm(forms.ModelForm):
    image = forms.ClearableFileInput(attrs={'class':'form-group', 'accept':'image/*', 'required': False})
    bio = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-group', 'rows': 3, 'required': False}))
    birthdate = forms.DateField(required=False)
    city = forms.CharField(max_length=255, required=False)
    location = PlainLocationField(based_fields=['city'], zoom=7, blank=True)
    class Meta:
        model = Profile
        fields = ['image', 'bio', 'birthdate', 'city', 'location']
    def __init__(self, *args, **kwargs):
        super(ProfileUpdateForm, self).__init__(*args, **kwargs)
        self.fields['bio'].initial = self.instance.bio
        self.fields['birthdate'].initial = self.instance.birthdate
        self.fields['city'].initial = self.instance.city
        self.fields['location'].initial = self.instance.location
    def save(self, commit=True):
        profile = super(ProfileUpdateForm, self).save(commit=False)
        profile.bio = self.cleaned_data['bio']
        profile.birthdate = self.cleaned_data['birthdate']
        profile.city = self.cleaned_data['city']
        profile.location = self.cleaned_data['location']
        if commit:
            profile.save()
        return profile  
