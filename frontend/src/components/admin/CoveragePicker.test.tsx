import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  CoveragePicker,
  type CoverageValue,
  type RegionData,
} from './CoveragePicker';

const regionData: RegionData = {
  countries: [
    {
      level: 'country',
      code: 'NI',
      name: 'Nicaragua',
      subregion_code: '013',
      subregion_name: 'Central America',
      region_code: '019',
      region_name: 'Americas',
    },
  ],
  subregions: [
    {
      level: 'subregion',
      code: '013',
      name: 'Central America',
      region_code: '019',
      region_name: 'Americas',
    },
  ],
  regions: [{ level: 'region', code: '019', name: 'Americas' }],
};

function StatefulPicker() {
  const [value, setValue] = useState<CoverageValue>({
    scope_level: '',
    scope_code: '',
  });
  return (
    <CoveragePicker
      data={regionData}
      value={value}
      onChange={setValue}
      label="Coverage"
    />
  );
}

describe('CoveragePicker', () => {
  afterEach(() => {
    cleanup();
  });

  it('scopes searchable options to the selected coverage level', async () => {
    const user = userEvent.setup();
    render(<StatefulPicker />);

    const codeInput = screen.getByLabelText('Coverage code');
    expect(codeInput).toBeDisabled();

    await user.selectOptions(
      screen.getByLabelText('Coverage level'),
      'country'
    );
    await user.click(codeInput);
    await user.type(codeInput, 'Nicaragua');

    expect(screen.getByRole('option', { name: /Nicaragua.*NI/ })).toBeVisible();
    expect(screen.queryByText('Central America')).not.toBeInTheDocument();
    expect(screen.queryByText('Americas')).not.toBeInTheDocument();
  });

  it('keeps the selected name and code visible after commit', async () => {
    const user = userEvent.setup();
    render(<StatefulPicker />);

    await user.selectOptions(
      screen.getByLabelText('Coverage level'),
      'country'
    );
    const codeInput = screen.getByLabelText('Coverage code');
    await user.click(codeInput);
    await user.type(codeInput, 'Nicaragua');
    fireEvent.mouseDown(screen.getByRole('option', { name: /Nicaragua.*NI/ }));

    expect(codeInput).toHaveValue('Nicaragua (NI)');
  });

  it('stores global coverage without a code', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CoveragePicker
        data={regionData}
        value={{ scope_level: '', scope_code: '' }}
        onChange={onChange}
      />
    );

    await user.selectOptions(screen.getByLabelText('Coverage level'), 'global');

    expect(onChange).toHaveBeenCalledWith({
      scope_level: 'global',
      scope_code: '',
    });
  });

  it('clears a committed coverage code with keyboard activation', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CoveragePicker
        data={regionData}
        value={{ scope_level: 'country', scope_code: 'NI' }}
        onChange={onChange}
      />
    );

    const clearButton = screen.getByRole('button', {
      name: 'Clear coverage code',
    });
    clearButton.focus();
    await user.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith({
      scope_level: 'country',
      scope_code: '',
    });
  });

  it('allows a manual code when the region taxonomy is unavailable', async () => {
    const user = userEvent.setup();

    function PickerWithoutTaxonomy() {
      const [value, setValue] = useState<CoverageValue>({
        scope_level: 'region',
        scope_code: '',
      });
      return <CoveragePicker data={null} value={value} onChange={setValue} />;
    }

    render(<PickerWithoutTaxonomy />);

    const codeInput = screen.getByLabelText('Coverage code');
    await user.type(codeInput, '019');

    expect(codeInput).toHaveValue('019');
    expect(
      screen.getByText('Region directory unavailable. Enter a code manually.')
    ).toBeInTheDocument();
  });
});
