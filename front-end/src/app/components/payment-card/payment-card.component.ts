import { CommonModule, CurrencyPipe } from '@angular/common'
import { Component, Inject } from '@angular/core'
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog'
import { PaymentService } from '../../services/payment/payment.service'
import { Router } from '@angular/router'

@Component({
    selector: 'app-payment-card',
    standalone: true,
    imports: [CurrencyPipe, CommonModule],
    templateUrl: './payment-card.component.html',
    styleUrls: ['./payment-card.component.css']
})
export class PaymentCardComponent {
    constructor(
        @Inject(MAT_DIALOG_DATA) public data: { payment: any },
        private readonly paymentService: PaymentService,
        private readonly dialogRef: MatDialogRef<PaymentCardComponent>,
        private readonly router: Router
    ) {}

    deletePayment(paymentId: string): void {
        this.paymentService.deletePayment(paymentId).subscribe({
            next: (response) => {
                if (response.message === 'Success') {
                    this.dialogRef.close({ action: 'delete', paymentId })
                }
            },
            error: (error) => {
                console.error('Error deleting payment:', error)
            }
        })
    }

    editPayment(paymentId: string): void {
        this.dialogRef.close({ action: 'edit', paymentId })
        this.router.navigate(['/edit-payment', paymentId])
    }
    Cancel() {
        this.dialogRef.close({ action: 'cancel' })
    }
}
