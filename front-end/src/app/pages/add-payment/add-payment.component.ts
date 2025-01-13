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
import { Payment } from '../../interfaces/payment'
import { PaymentService } from '../../services/payment/payment.service'

@Component({
    selector: 'app-add-payment',
    standalone: true,
    imports: [ReactiveFormsModule, NgFor],
    templateUrl: './add-payment.component.html',
    styleUrls: ['./add-payment.component.css']
})
export class AddPaymentComponent {
    paymentForm!: FormGroup
    country_iso2: { [key: string]: string } = {}
    country_cities: { [key: string]: string[] } = {}
    countries: string[] = []
    cities: string[] = []
    currencies: string[] = []
    filteredCurrencies: string[] = []

    constructor(
        private readonly fb: FormBuilder,
        private readonly router: Router,
        private readonly autoCompleteService: AutocompletionService,
        private readonly paymentService: PaymentService
    ) {}

    ngOnInit(): void {
        this.paymentForm = this.fb.group({
            payee_first_name: ['', Validators.required],
            payee_last_name: ['', Validators.required],
            payee_payment_status: ['pending', Validators.required],
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
        this.paymentForm.get('payee_payment_status')?.disable()
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
        this.autoCompleteService.getCountries().subscribe({
            next: (response: any) => {
                this.countries = response.data.map((item: any) => {
                    this.country_iso2[item.country as string] = item.iso2
                    this.country_cities[item.country as string] = item.cities
                })
                this.countries = Object.keys(this.country_iso2)
            },
            error: (err) => console.error('Error loading countries:', err)
        })
    }

    onCountryChange(): void {
        const selectedCountry = this.paymentForm.get('payee_country')?.value
        if (selectedCountry) {
            if (this.country_cities[selectedCountry]) {
                this.cities = this.country_cities[selectedCountry]
            }
        }
    }

    loadCurrencies(): void {
        this.autoCompleteService.getCurrencies().subscribe({
            next: (response: any) => {
                const uniqueCurrencies = new Set(
                    response
                        .map((item: any) => {
                            if (
                                item?.currencies &&
                                typeof item.currencies === 'object'
                            ) {
                                const currencyKeys = Object.keys(
                                    item.currencies
                                )
                                return currencyKeys.length > 0
                                    ? currencyKeys[0]
                                    : ''
                            }
                            return ''
                        })
                        .filter((currency: string) => currency)
                )

                this.currencies = Array.from(uniqueCurrencies) as string[]
                this.filteredCurrencies = [...this.currencies]
            },
            error: (err) => console.error('Error loading currencies:', err)
        })
    }

    onCurrencyInputChange(event: Event): void {
        const input = event.target as HTMLInputElement
        const inputValue = input.value

        this.filteredCurrencies = this.currencies.filter((currency) =>
            currency.toLowerCase().startsWith(inputValue.toLowerCase())
        )
    }

    onSubmit(): void {
        if (this.paymentForm.valid) {
            const rawData = this.paymentForm.getRawValue()

            const paymentData: Payment = {
                payee_first_name: rawData.payee_first_name,
                payee_last_name: rawData.payee_last_name,
                payee_payment_status: rawData.payee_payment_status || 'pending',
                payee_added_date_utc: new Intl.DateTimeFormat('en-US', {
                    month: 'short',
                    day: '2-digit',
                    year: 'numeric',
                    hour: 'numeric',
                    minute: 'numeric',
                    hour12: true
                }).format(new Date()),
                payee_due_date: rawData.payee_due_date,
                payee_address_line_1: rawData.payee_address_line_1,
                payee_address_line_2: rawData.payee_address_line_2 || '',
                payee_city: rawData.payee_city,
                payee_country: this.country_iso2[rawData.payee_country],
                payee_province_or_state: rawData.payee_province_or_state || '',
                payee_postal_code: rawData.payee_postal_code,
                payee_phone_number: rawData.payee_phone_number.startsWith('+')
                    ? rawData.payee_phone_number
                    : '+' + rawData.payee_phone_number,
                payee_email: rawData.payee_email,
                currency: rawData.currency,
                discount_percent: rawData.discount_percent || 0,
                tax_percent: rawData.tax_percent || 0,
                due_amount: rawData.due_amount,
                total_amount: 0
            }

            this.paymentService.addPayment(paymentData).subscribe({
                next: () => {
                    this.router.navigate(['/'])
                },
                error: (err) => {
                    console.error('Error adding payment:', err)
                    alert('Error adding payment: ' + err.error.detail)
                }
            })
        } else {
            alert('Please fill all required fields correctly.')
        }
    }
}
