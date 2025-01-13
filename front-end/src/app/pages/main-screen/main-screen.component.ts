import { Component, ElementRef, ViewChild } from '@angular/core'
import { MatDialog, MatDialogModule } from '@angular/material/dialog'
import { PaymentService } from '../../services/payment/payment.service'
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms'
import { CommonModule, NgFor } from '@angular/common'
import { VisibilityComponent } from '../../components/visibility/visibility.component'
import { Payment } from '../../interfaces/payment'
import { PaymentCardComponent } from '../../components/payment-card/payment-card.component'

@Component({
    selector: 'app-main-screen',
    imports: [
        MatDialogModule,
        ReactiveFormsModule,
        CommonModule,
        NgFor,
        VisibilityComponent
    ],
    standalone: true,
    templateUrl: './main-screen.component.html',
    styleUrls: ['./main-screen.component.css']
})
export class MainScreenComponent {
    @ViewChild('fileInput') fileInput!: ElementRef
    payments: Map<string, Payment> = new Map()
    filteredPayments: Map<string, Payment> = new Map()
    paymentList: any[] = []
    totalDue: number = 0
    filterForm!: FormGroup

    currentPage: number = 1
    itemsPerPage: number = 10
    totalPages: number = 1
    paginatedPaymentList: any[] = []
    visiblePages: number[] = []

    constructor(
        private readonly paymentService: PaymentService,
        private readonly fb: FormBuilder,
        private readonly dialog: MatDialog
    ) {}

    ngOnInit(): void {
        this.filterForm = this.fb.group({
            status: [''],
            search: ['']
        })
        this.loadPayments()
    }

    openPaymentCard(payment: Payment): void {
        const dialogRef = this.dialog.open(PaymentCardComponent, {
            width: '400px',
            data: { payment },
            disableClose: true
        })
        dialogRef.afterClosed().subscribe((result) => {
            if (result) {
                switch (result.action) {
                    case 'delete':
                        this.removePayment(result.paymentId)
                        break
                    case 'edit':
                        console.log('Edit logic can be implemented here.')
                        break
                    case 'cancel':
                        console.log('Dialog closed with no changes.')
                        break
                }
            }
        })
    }

    removePayment(paymentId: string): void {
        this.payments.delete(paymentId)
        this.filteredPayments.delete(paymentId)
        this.paymentList = Array.from(this.filteredPayments.values())
        this.updatePagination()
    }

    loadPayments(): void {
        this.paymentService.getAllPayments().subscribe({
            next: (response) => {
                this.paymentList = response as Payment[]
                this.payments = new Map(
                    this.paymentList.map((payment) => [payment.id, payment])
                )
                this.filteredPayments = new Map(this.payments)
                this.paymentList = Array.from(this.filteredPayments.values())
                this.updatePagination()
            },
            error: (err) => console.error('Error loading payments:', err)
        })
    }

    applyFilters(): void {
        const filters = this.filterForm.value

        this.filteredPayments = new Map(this.payments)
        if (filters.status) {
            this.filteredPayments = new Map(
                Array.from(this.filteredPayments).filter(
                    ([id, payment]) =>
                        payment.payee_payment_status === filters.status
                )
            )
        }

        if (filters.search) {
            const searchTerm = filters.search.toLowerCase()
            this.filteredPayments = new Map(
                Array.from(this.filteredPayments).filter(([id, payment]) => {
                    return (
                        payment.payee_first_name
                            .toLowerCase()
                            .includes(searchTerm) ||
                        payment.payee_last_name
                            .toLowerCase()
                            .includes(searchTerm) ||
                        payment.payee_address_line_1
                            .toLowerCase()
                            .includes(searchTerm) ||
                        payment.payee_address_line_2
                            ?.toLowerCase()
                            .includes(searchTerm)
                    )
                })
            )
        }

        this.paymentList = Array.from(this.filteredPayments.values())
        this.updatePagination()
    }

    triggerFileInput(paymentId: string): void {
        const fileInput = this.fileInput.nativeElement as HTMLInputElement
        fileInput.click()
    }

    uploadEvidence(paymentId: string, event: Event): void {
        const input = event.target as HTMLInputElement
        if (input?.files?.length) {
            const file = input.files[0]
            console.log(`Uploading evidence for payment ID ${paymentId}:`, file)
        } else {
            console.error('No file selected.')
        }
    }

    downloadEvidence(paymentId: string): void {
        this.paymentService.downloadEvidence(paymentId).subscribe({
            next: (response) => {
                const blob = new Blob([response], {
                    type: 'application/pdf'
                })
                const url = window.URL.createObjectURL(blob)
                window.open(url)
            },
            error: (err) => console.error('Error downloading evidence:', err)
        })
    }
    callToggleVisibility(paymentId: string): void {
        const payment = this.payments.get(paymentId) as Payment
        this.openPaymentCard(payment)
    }
    updatePagination(): void {
        this.totalPages = Math.ceil(this.paymentList.length / this.itemsPerPage)
        this.updateVisiblePages()
        this.paginatedPaymentList = this.getPaginatedData()
    }

    updateVisiblePages(): void {
        const maxVisiblePages = 3
        let startPage = Math.max(this.currentPage - 1, 1)
        let endPage = Math.min(this.currentPage + 1, this.totalPages)

        if (this.totalPages > maxVisiblePages) {
            if (this.currentPage === 1) {
                endPage = startPage + maxVisiblePages - 1
            } else if (this.currentPage === this.totalPages) {
                startPage = endPage - maxVisiblePages + 1
            }
        }

        this.visiblePages = []
        for (let i = startPage; i <= endPage; i++) {
            this.visiblePages.push(i)
        }
    }

    changePage(page: number): void {
        if (page > 0 && page <= this.totalPages) {
            this.currentPage = page
            this.updateVisiblePages()
            this.paginatedPaymentList = this.getPaginatedData()
        }
    }

    getPaginatedData(): Payment[] {
        const startIndex = (this.currentPage - 1) * this.itemsPerPage
        const endIndex = startIndex + this.itemsPerPage
        return this.paymentList.slice(startIndex, endIndex)
    }
}
