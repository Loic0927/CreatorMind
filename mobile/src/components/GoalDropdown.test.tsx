import { fireEvent, render } from '@testing-library/react-native';
import { GoalDropdown } from './GoalDropdown';

describe('GoalDropdown', () => {
  it('opens and selects Other', async () => {
    const toggle = jest.fn(); const select = jest.fn();
    const { getByLabelText, getByText, rerender } = await render(<GoalDropdown value="" open={false} onToggle={toggle} onSelect={select} />);
    await fireEvent.press(getByLabelText('Choose content goal'));
    expect(toggle).toHaveBeenCalled();
    await rerender(<GoalDropdown value="" open onToggle={toggle} onSelect={select} />);
    await fireEvent.press(getByText('Other'));
    expect(select).toHaveBeenCalledWith('Other');
  });
});
