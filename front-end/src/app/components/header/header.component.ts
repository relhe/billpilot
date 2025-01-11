import { Component } from '@angular/core'
import { Router } from '@angular/router'

@Component({
    selector: 'app-header',
    imports: [],
    templateUrl: './header.component.html',
    standalone: true,
    styleUrl: './header.component.css'
})
export class HeaderComponent {
    constructor(private readonly router: Router) {}

    navigateTo(path: string): void {
        this.router.navigate([path])
    }
}
