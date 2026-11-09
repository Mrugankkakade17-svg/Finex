export interface ConsentRequest {
  consentGiven: boolean;
}

export interface ConsentResponse {
  consentGiven: boolean;
  saved: boolean;
}

export const consentService = {
  saveConsent: async (
    request: ConsentRequest
  ): Promise<ConsentResponse> => {
    // Mock service response while backend is pending.
    await new Promise((resolve) => setTimeout(resolve, 500));

    if (!request.consentGiven) {
      throw new Error(
        'Required consent must be provided.'
      );
    }

    return {
      consentGiven: true,
      saved: true,
    };
  },
};