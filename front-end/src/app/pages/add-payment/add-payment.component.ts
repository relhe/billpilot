import { Component } from '@angular/core'
import {
    ReactiveFormsModule,
    FormBuilder,
    FormGroup,
    Validators
} from '@angular/forms'
import { Router } from '@angular/router'
import { AutocompletionService } from '../../services/autocompletion/autocompletion.service'
import { NgFor } from '@angular/common'

@Component({
    selector: 'app-add-payment',
    standalone: true,
    imports: [ReactiveFormsModule, NgFor],
    templateUrl: './add-payment.component.html',
    styleUrls: ['./add-payment.component.css']
})
export class AddPaymentComponent {
    paymentForm!: FormGroup
    countries: string[] = []
    cities: string[] = []
    currencies: string[] = []

    constructor(
        private readonly fb: FormBuilder,
        private readonly router: Router,
        private readonly autoCompleteService: AutocompletionService
    ) {}

    ngOnInit(): void {
        this.paymentForm = this.fb.group({
            payee_first_name: ['', Validators.required],
            payee_last_name: ['', Validators.required],
            payee_payment_status: [{ value: 'pending' }, Validators.required],
            payee_added_date_utc: [
                { value: new Date().toISOString(), disabled: true },
                Validators.required
            ],
            payee_due_date: ['', [Validators.required, this.validateDate]],
            payee_address_line_1: ['', Validators.required],
            payee_address_line_2: [''],
            payee_city: ['', Validators.required],
            payee_country: ['', Validators.required],
            payee_province_or_state: [''],
            payee_postal_code: ['', Validators.required],
            payee_phone_number: [
                '',
                [Validators.required, Validators.pattern(/^\+?[1-9]\d{1,14}$/)]
            ],
            payee_email: ['', [Validators.required, Validators.email]],
            currency: ['', Validators.required],
            discount_percent: [0, [Validators.min(0), Validators.max(100)]],
            tax_percent: [0, [Validators.min(0), Validators.max(100)]],
            due_amount: [0, [Validators.required, Validators.min(0)]],
            total_due: [{ value: 0, disabled: true }]
        })

        // Load initial data
        this.loadCountries()
        this.loadCurrencies()

        // Recalculate total due whenever relevant fields change
        this.paymentForm.valueChanges.subscribe(() => {
            this.calculateTotalDue()
        })
        this.paymentForm.get('payee_payment_status')?.disable() // Disable the control
    }

    private validateDate(control: any): { [key: string]: boolean } | null {
        const isValid = /^\d{4}-\d{2}-\d{2}$/.test(control.value)
        return isValid ? null : { invalidDate: true }
    }

    private calculateTotalDue(): void {
        const dueAmount = this.paymentForm.get('due_amount')?.value || 0
        const discountPercent =
            this.paymentForm.get('discount_percent')?.value || 0
        const taxPercent = this.paymentForm.get('tax_percent')?.value || 0

        const discount = (dueAmount * discountPercent) / 100
        const tax = (dueAmount * taxPercent) / 100
        const totalDue = dueAmount - discount + tax

        this.paymentForm
            .get('total_due')
            ?.setValue(totalDue.toFixed(2), { emitEvent: false })
    }

    loadCountries(): void {
        console.log('Loading countries for bb tat...')
        this.autoCompleteService.getCountries().subscribe({
            next: (response: any) => {
                console.log('Countries:')
                this.countries = response.data.map((item: any) => item.country)
            },
            error: (err) => console.error('Error loading countries:', err)
        })
        console.log('Loading countries for bb tat...')
    }

    onCountryChange(): void {
        const selectedCountry = this.paymentForm.get('payee_country')?.value
        if (selectedCountry) {
            this.autoCompleteService.getCities(selectedCountry).subscribe({
                next: (response: any) => {
                    this.cities = response.data
                },
                error: (err) => console.error('Error loading cities:', err)
            })
        }
    }

    loadCurrencies(): void {
        this.autoCompleteService.getCurrencies().subscribe({
            next: (response: any) => {
                this.currencies = response
                    .map((item: any) => item.currencies?.[0]?.code)
                    .filter(Boolean)
            },
            error: (err) => console.error('Error loading currencies:', err)
        })
    }

    onSubmit(): void {
        if (this.paymentForm.valid) {
            console.log('Payment Data:', this.paymentForm.getRawValue())
            alert('Payment added successfully!')
            this.router.navigate(['/add-payment'])
        } else {
            alert('Please fill all required fields correctly.')
        }
    }
}
