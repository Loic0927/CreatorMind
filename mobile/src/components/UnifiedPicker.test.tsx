import { fireEvent, render } from '@testing-library/react-native';
import { UnifiedPicker } from './UnifiedPicker';

const options = [
  { value: 'one', label: 'One' },
  { value: 'two', label: 'Two' },
  { value: 'other', label: 'Other' },
];

describe('UnifiedPicker', () => {
  it('opens a native bottom sheet and selects one value', async () => {
    const change = jest.fn();
    const view = await render(<UnifiedPicker label="Goal" options={options} value="one" onChange={change} />);
    await fireEvent.press(view.getByLabelText('Choose Goal'));
    expect(view.getByLabelText('Close Goal')).toBeTruthy();
    await fireEvent.press(view.getByText('Two'));
    expect(change).toHaveBeenCalledWith('two');
  });

  it('supports multi-select max, chips, and Done', async () => {
    const change = jest.fn();
    const view = await render(<UnifiedPicker label="Tone" options={options} values={['one', 'two']} onValuesChange={change} multiple max={2} />);
    expect(view.getByText('One')).toBeTruthy();
    expect(view.getByText('Two')).toBeTruthy();
    await fireEvent.press(view.getByLabelText('Choose Tone'));
    expect(view.getByText('2 of 2 selected')).toBeTruthy();
    expect(view.getByText('Other').parent?.props.accessibilityState.disabled).toBe(true);
    await fireEvent.press(view.getByText('Done'));
  });

  it('reveals and updates the Other field without changing its value contract', async () => {
    const update = jest.fn();
    const view = await render(<UnifiedPicker label="Category" options={options} value="other" onChange={jest.fn()} otherOptionValue="other" otherValue="Custom" onOtherValueChange={update} />);
    await fireEvent.changeText(view.getByLabelText('Category other value'), 'Creator');
    expect(update).toHaveBeenCalledWith('Creator');
  });

  it('exposes disabled and error states', async () => {
    const view = await render(<UnifiedPicker label="Sort" options={options} disabled error="Choose a sort" />);
    expect(view.getByLabelText('Choose Sort').props.accessibilityState.disabled).toBe(true);
    expect(view.getByRole('alert').props.children).toBe('Choose a sort');
  });
});
