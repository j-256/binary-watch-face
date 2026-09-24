# Heart-history controls update

## Binary Pulse 0.4.0-history-prototype.2

- Add Faint graph brightness alongside Subtle and Clear, and a 7.5% decimal-backdrop opacity option
- Lower the history trace and keep its background provider dedicated to Binary Heart History
- Put frequently adjusted appearance controls earlier in the editor and clarify independent numeric heart-rate visibility under Heart rate & battery

The graph remains hidden in AOD. Heart rate: Active + AOD keeps the numeric readout visible independently. Wear OS places Layout & brightness and Complications at the end of its editor despite their source ordering.

## Binary Heart History 0.3.0-prototype

- Add a round button for cycling time windows directly from the chart
- Add optional vertical ticks, dots, or triangles, with Sparse, Regular, and Dense spacing remembered for each window
- Center choice-menu labels and keep Cancel in the same scrolling list as the options
- Preserve a usable chart and accessible controls on small displays with enlarged text
- Include marker and spacing preferences when detecting changes that invalidate an active battery comparison

These updates retain the existing package identities and saved setting IDs. They use the Wear OS internal testing tracks for Binary Pulse and Binary Heart History. The original Binary application has a separate release process.
