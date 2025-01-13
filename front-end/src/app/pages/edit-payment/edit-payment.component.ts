import { Component } from '@angular/core'
import {
    ReactiveFormsModule,
    FormBuilder,
    FormGroup,
    Validators
} from '@angular/forms'
import { ActivatedRoute, Router } from '@angular/router'
import { AutocompletionService } from '../../services/autocompletion/autocompletion.service'
import { PaymentService } from '../../services/payment/payment.service'
import { NgFor, NgIf } from '@angular/common'

@Component({
    selector: 'app-edit-payment',
    imports: [ReactiveFormsModule, NgIf, NgFor],
    standalone: true,
    templateUrl: './edit-payment.component.html',
    styleUrl: './edit-payment.component.css'
})
export class EditPaymentComponent {
    editPaymentForm!: FormGroup
    country_iso2: { [key: string]: string } = {}
    countries: string[] = []
    country_cities: { [key: string]: string[] } = {}
    countryNames: string[] = []
    cities: string[] = []
    currencies: string[] = []
    evidenceFile: File | null = null
    paymentId: string = ''
    editablePayment: any

    constructor(
        private readonly fb: FormBuilder,
        private readonly router: Router,
        private readonly route: ActivatedRoute,
        private readonly autoCompleteService: AutocompletionService,
        private readonly paymentService: PaymentService
    ) {}

    ngOnInit(): void {
        this.paymentId = this.route.snapshot.params['id']
        this.editPaymentForm = this.fb.group({
            payee_first_name: ['', Validators.required],
            payee_last_name: ['', Validators.required],
            payee_payment_status: ['', Validators.required],
            payee_address_line_1: ['', Validators.required],
            payee_address_line_2: [''],
            payee_city: ['', Validators.required],
            payee_country: ['', Validators.required],
            currency: ['', Validators.required],
            due_amount: [0, [Validators.required, Validators.min(0)]]
        })

        this.loadPaymentData()
        this.loadCountries()
    }

    loadPaymentData(): void {
        if (this.paymentId === '1') {
            this.paymentService.getAllPayments().subscribe({
                next: (payments) => {
                    const pendingPayment = payments.find(
                        (payment: any) =>
                            payment.payee_payment_status === 'pending'
                    )

                    if (pendingPayment) {
                        this.editablePayment = pendingPayment
                        this.editPaymentForm.patchValue(pendingPayment)
                        this.paymentId = pendingPayment.id
                    } else {
                        this.editablePayment = payments[0]
                        this.editPaymentForm.patchValue(payments[0])
                    }
                },
                error: (err) =>
                    console.error('Error loading all payments:', err)
            })
        } else {
            this.paymentService.getPaymentById(this.paymentId).subscribe({
                next: (payment) => {
                    if (payment.payee_payment_status !== 'overdue') {
                        this.editablePayment = payment
                        this.editPaymentForm.patchValue(payment)
                    } else {
                        alert('Overdue payments cannot be edited.')
                        this.router.navigate(['/'])
                    }
                },
                error: (err) =>
                    console.error('Error loading payment by ID:', err)
            })
        }
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
        const selectedCountry = this.editPaymentForm.get('payee_country')?.value
        if (selectedCountry) {
            if (this.country_cities[selectedCountry]) {
                this.cities = this.country_cities[selectedCountry]
            }
        }
    }

    updateDifferentFields(oldPayment: any, newPayment: any): any {
        const updatedFields: any = oldPayment
        for (const key in newPayment) {
            if (newPayment[key] !== oldPayment[key]) {
                updatedFields[key] = newPayment[key]
            }
        }
        delete updatedFields.id

        return updatedFields
    }

    onFileUpload(event: Event): void {
        const input = event.target as HTMLInputElement
        if (input.files && input.files.length > 0) {
            const file = input.files[0]
            const allowedMimeTypes = [
                'application/pdf',
                'image/png',
                'image/jpeg'
            ]

            if (!allowedMimeTypes.includes(file.type)) {
                alert('Invalid file type. Only PDF, PNG, and JPG are allowed.')
                this.evidenceFile = null
                return
            }

            this.evidenceFile = file
        } else {
            this.evidenceFile = null
        }
    }
    onSubmit(): void {
        if (this.editPaymentForm.valid) {
            const paymentData = this.editPaymentForm.value

            if (
                paymentData.payee_payment_status === 'completed' &&
                !this.evidenceFile
            ) {
                alert(
                    'An evidence file is required when marking payment as completed.'
                )
                return
            }

            if (
                paymentData.payee_payment_status === 'completed' &&
                this.evidenceFile
            ) {
                const allowedMimeTypes = [
                    'application/pdf',
                    'image/png',
                    'image/jpeg'
                ]
                if (!allowedMimeTypes.includes(this.evidenceFile.type)) {
                    alert(
                        'Invalid file type. Only PDF, PNG, and JPG are allowed.'
                    )
                    return
                }

                const formData = new FormData()
                formData.append(
                    'file',
                    this.evidenceFile,
                    this.evidenceFile.name
                )

                this.paymentService
                    .uploadEvidence(this.paymentId, formData)
                    .subscribe({
                        next: () => {
                            const updatedFields = this.updateDifferentFields(
                                this.editablePayment,
                                paymentData
                            )

                            this.paymentService
                                .updatePayment(this.paymentId, updatedFields)
                                .subscribe({
                                    next: () => {
                                        alert(
                                            'Payment updated successfully with evidence!'
                                        )
                                        this.router.navigate(['/'])
                                    },
                                    error: (err) => {
                                        console.error(
                                            'Error updating payment:',
                                            err
                                        )
                                        alert(
                                            'Error updating payment: ' +
                                                err.error?.detail
                                        )
                                    }
                                })
                        },
                        error: (err) => {
                            console.error('Error uploading evidence:', err)
                            alert(
                                'Error uploading evidence: ' + err.error?.detail
                            )
                        }
                    })
            } else {
                const updatedFields = this.updateDifferentFields(
                    this.editablePayment,
                    paymentData
                )

                this.paymentService
                    .updatePayment(this.paymentId, updatedFields)
                    .subscribe({
                        next: () => {
                            alert('Payment updated successfully!')
                            this.router.navigate(['/'])
                        },
                        error: (err) => {
                            console.error('Error updating payment:', err)
                            alert(
                                'Error updating payment: ' + err.error?.detail
                            )
                        }
                    })
            }
        } else {
            alert('Please fill all required fields correctly.')
        }
    }
}
