import { Injectable, Injector } from '@angular/core'
import { HttpClient } from '@angular/common/http'

@Injectable({
    providedIn: 'root'
})
export class AutocompletionService {
    private http!: HttpClient
    private readonly countriesUrl =
        'https://countriesnow.space/api/v0.1/countries'
    private readonly currenciesUrl = 'https://restcountries.com/v3.1/all'

    constructor(private readonly injector: Injector) {}

    private getHttp(): HttpClient {
        if (!this.http) {
            this.http = this.injector.get(HttpClient)
        }
        return this.http
    }

    getCountries() {
        console.log('getCountries dada t bien ri')
        return this.getHttp().get(`${this.countriesUrl}/info`)
    }

    getCities(country: string) {
        return this.getHttp().post(`${this.countriesUrl}/cities`, { country })
    }

    getCurrencies() {
        console.log('getCountries dada t bien ri ddd')

        return this.getHttp().get(this.currenciesUrl)
    }
}
