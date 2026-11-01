Feature: Refund flow

  Scenario: Customer requests a refund for a delivered order
    Given a user is on the orders page
    When the user opens their most recent delivered order
    And the user hovers over the order, finds the refund control, clicks it to open the refund page
    Then the refund page should be visible
    When the user submits the refund with reason "Damaged on arrival"
    Then the confirmation page should be visible
    Then the results table should be shown with the following values
      | Status      | Order | Reference | Amount |
      | Successful  | <id>  | <ref>     | 272.00 |
