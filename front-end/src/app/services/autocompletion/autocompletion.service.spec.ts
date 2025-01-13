import { TestBed } from '@angular/core/testing';

import { AutocompletionService } from './autocompletion.service';

describe('AutocompletionService', () => {
  let service: AutocompletionService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(AutocompletionService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
