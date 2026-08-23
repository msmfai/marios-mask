package ai.smf.mariosmask;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int CHOOSE_SM64 = 100;
    private static final int CHOOSE_OOT = 101;
    private static final int CHOOSE_MM = 102;
    private static final int CHOOSE_OUTPUT = 103;
    private static final long MAX_INPUT_BYTES = 128L * 1024L * 1024L;

    static {
        System.loadLibrary("marios_mask_builder");
    }

    private static native String nativeBuild(
            String sm64, String oot, String mm, String output,
            int red, int green, int blue);

    private final ExecutorService builder = Executors.newSingleThreadExecutor();
    private Uri sm64Uri;
    private Uri ootUri;
    private Uri mmUri;
    private Button sm64Button;
    private Button ootButton;
    private Button mmButton;
    private Button buildButton;
    private TextView statusView;
    private TextView colorValue;
    private final int[] marioColor = {24, 88, 22};
    private final SeekBar[] colorSliders = new SeekBar[3];

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) {
            sm64Uri = parseUri(state.getString("sm64"));
            ootUri = parseUri(state.getString("oot"));
            mmUri = parseUri(state.getString("mm"));
            marioColor[0] = state.getInt("marioRed", 24);
            marioColor[1] = state.getInt("marioGreen", 88);
            marioColor[2] = state.getInt("marioBlue", 22);
        }
        setContentView(createContent());
        refreshSelections();
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putString("sm64", sm64Uri == null ? null : sm64Uri.toString());
        state.putString("oot", ootUri == null ? null : ootUri.toString());
        state.putString("mm", mmUri == null ? null : mmUri.toString());
        state.putInt("marioRed", marioColor[0]);
        state.putInt("marioGreen", marioColor[1]);
        state.putInt("marioBlue", marioColor[2]);
    }

    @Override
    protected void onDestroy() {
        builder.shutdown();
        super.onDestroy();
    }

    private View createContent() {
        int margin = dp(22);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(margin, margin, margin, margin);

        TextView title = text("Mario's Mask Builder", 28, Color.rgb(55, 36, 23));
        title.setTypeface(title.getTypeface(), android.graphics.Typeface.BOLD);
        content.addView(title);

        TextView intro = text(
            "Choose your own NTSC-US Super Mario 64 and Majora's Mask ROMs, plus any compatible retail Ocarina of Time ROM. " +
                "They stay on this device and are combined locally.",
            16,
            Color.DKGRAY
        );
        intro.setPadding(0, dp(10), 0, dp(20));
        content.addView(intro);

        sm64Button = button("Choose Super Mario 64", view -> chooseRom(CHOOSE_SM64));
        content.addView(sm64Button);
        content.addView(spacer());

        ootButton = button("Choose Ocarina of Time (any version)", view -> chooseRom(CHOOSE_OOT));
        content.addView(ootButton);
        content.addView(spacer());

        mmButton = button("Choose Majora's Mask", view -> chooseRom(CHOOSE_MM));
        content.addView(mmButton);
        content.addView(spacer());

        TextView colorTitle = text("Mario colour", 17, Color.DKGRAY);
        colorTitle.setTypeface(colorTitle.getTypeface(), android.graphics.Typeface.BOLD);
        content.addView(colorTitle);
        TextView colorDisclaimer = text(
            "Mario canonically wears Link's colours in Mario's Mask, and NPCs will refer " +
                "to his green clothes. Original red Mario is available for players who " +
                "would prefer it.",
            14,
            Color.DKGRAY
        );
        colorDisclaimer.setPadding(0, dp(5), 0, dp(8));
        content.addView(colorDisclaimer);
        LinearLayout presets = new LinearLayout(this);
        presets.setOrientation(LinearLayout.HORIZONTAL);
        Button green = button("L(ink) Is Real", view -> setMarioColor(24, 88, 22));
        Button red = button("Original", view -> setMarioColor(255, 0, 0));
        presets.addView(green, new LinearLayout.LayoutParams(0, dp(54), 1));
        presets.addView(red, new LinearLayout.LayoutParams(0, dp(54), 1));
        content.addView(presets);
        TextView customColor = text("Custom colour", 15, Color.DKGRAY);
        customColor.setPadding(0, dp(8), 0, 0);
        content.addView(customColor);
        content.addView(colorChannel("Red", 0));
        content.addView(colorChannel("Green", 1));
        content.addView(colorChannel("Blue", 2));
        colorValue = text("", 15, Color.DKGRAY);
        content.addView(colorValue);
        updateColorControls();
        content.addView(spacer());

        buildButton = button("Build Mario's Mask", view -> chooseOutput());
        content.addView(buildButton);

        statusView = text("Choose all three ROMs to begin.", 15, Color.DKGRAY);
        statusView.setPadding(0, dp(18), 0, dp(8));
        statusView.setGravity(Gravity.START);
        statusView.setTextIsSelectable(true);
        content.addView(statusView);

        TextView formats = text(
            "Accepted inputs: .z64, .v64, .n64, .rom, .zip, and .gz. " +
                "The finished .z64 can be opened in an Android N64 emulator or copied to a flash cart.",
            13,
            Color.GRAY
        );
        formats.setPadding(0, dp(8), 0, 0);
        content.addView(formats);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(content);
        return scroll;
    }

    private Button button(String label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(16);
        button.setMinHeight(dp(54));
        button.setOnClickListener(listener);
        return button;
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setLineSpacing(0, 1.12f);
        return view;
    }

    private View spacer() {
        View view = new View(this);
        view.setLayoutParams(new LinearLayout.LayoutParams(1, dp(10)));
        return view;
    }

    private View colorChannel(String label, int component) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        TextView name = text(label, 14, Color.DKGRAY);
        name.setGravity(Gravity.CENTER_VERTICAL);
        row.addView(name, new LinearLayout.LayoutParams(dp(58), dp(42)));
        SeekBar slider = new SeekBar(this);
        slider.setMax(255);
        slider.setProgress(marioColor[component]);
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int value, boolean fromUser) {
                if (fromUser) {
                    marioColor[component] = value;
                    updateColorControls();
                }
            }
            @Override public void onStartTrackingTouch(SeekBar bar) {}
            @Override public void onStopTrackingTouch(SeekBar bar) {}
        });
        colorSliders[component] = slider;
        row.addView(slider, new LinearLayout.LayoutParams(0, dp(42), 1));
        return row;
    }

    private void setMarioColor(int red, int green, int blue) {
        marioColor[0] = red;
        marioColor[1] = green;
        marioColor[2] = blue;
        updateColorControls();
    }

    private void updateColorControls() {
        for (int i = 0; i < colorSliders.length; i++) {
            if (colorSliders[i] != null && colorSliders[i].getProgress() != marioColor[i]) {
                colorSliders[i].setProgress(marioColor[i]);
            }
        }
        if (colorValue != null) {
            colorValue.setText(String.format("Custom  #%02X%02X%02X", marioColor[0], marioColor[1], marioColor[2]));
            colorValue.setBackgroundColor(Color.rgb(marioColor[0], marioColor[1], marioColor[2]));
            colorValue.setTextColor((marioColor[0] + marioColor[1] + marioColor[2]) < 360 ? Color.WHITE : Color.BLACK);
            colorValue.setPadding(dp(10), dp(6), dp(10), dp(6));
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void chooseRom(int requestCode) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, requestCode);
    }

    private void chooseOutput() {
        if (sm64Uri == null || ootUri == null || mmUri == null) {
            setStatus("Choose all three ROMs first.", true);
            return;
        }
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/octet-stream");
        intent.putExtra(Intent.EXTRA_TITLE, "Marios-Mask.z64");
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        startActivityForResult(intent, CHOOSE_OUTPUT);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            return;
        }
        Uri uri = data.getData();
        if (requestCode == CHOOSE_SM64 || requestCode == CHOOSE_OOT || requestCode == CHOOSE_MM) {
            persistReadPermission(uri, data.getFlags());
            if (requestCode == CHOOSE_SM64) {
                sm64Uri = uri;
            } else if (requestCode == CHOOSE_OOT) {
                ootUri = uri;
            } else {
                mmUri = uri;
            }
            refreshSelections();
        } else if (requestCode == CHOOSE_OUTPUT) {
            startBuild(uri);
        }
    }

    private void persistReadPermission(Uri uri, int flags) {
        int granted = flags & Intent.FLAG_GRANT_READ_URI_PERMISSION;
        try {
            getContentResolver().takePersistableUriPermission(uri, granted);
        } catch (SecurityException ignored) {
            // Some document providers grant access for the Activity lifetime only.
        }
    }

    private void refreshSelections() {
        if (sm64Button == null) {
            return;
        }
        sm64Button.setText(sm64Uri == null ? "Choose Super Mario 64" : "Super Mario 64: " + displayName(sm64Uri));
        ootButton.setText(ootUri == null ? "Choose Ocarina of Time (any version)" : "Ocarina of Time: " + displayName(ootUri));
        mmButton.setText(mmUri == null ? "Choose Majora's Mask" : "Majora's Mask: " + displayName(mmUri));
        buildButton.setEnabled(sm64Uri != null && ootUri != null && mmUri != null);
        if (sm64Uri != null && ootUri != null && mmUri != null) {
            setStatus("Ready. Choose where to save the finished game.", false);
        }
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (column >= 0) {
                    return cursor.getString(column);
                }
            }
        } catch (RuntimeException ignored) {
            // Fall back to the final URI path segment.
        }
        String segment = uri.getLastPathSegment();
        return segment == null ? "selected file" : segment;
    }

    private void startBuild(Uri outputUri) {
        final int red = marioColor[0];
        final int green = marioColor[1];
        final int blue = marioColor[2];
        setBuilding(true);
        setStatus("Reading and validating all three ROMs…", false);
        builder.execute(() -> {
            File work = new File(getCacheDir(), "build-" + System.nanoTime());
            try {
                if (!work.mkdirs()) {
                    throw new IOException("Could not create temporary build storage.");
                }
                File sm64 = new File(work, "sm64.input");
                File oot = new File(work, "oot.input");
                File mm = new File(work, "mm.input");
                File output = new File(work, "Marios-Mask.z64");
                copyInput(sm64Uri, sm64);
                copyInput(ootUri, oot);
                copyInput(mmUri, mm);

                runOnUiThread(() -> setStatus("Building Mario's Mask locally…", false));
                String error = nativeBuild(
                        sm64.getAbsolutePath(), oot.getAbsolutePath(), mm.getAbsolutePath(),
                        output.getAbsolutePath(),
                        red, green, blue);
                if (error == null) {
                    throw new IOException("The native builder could not return a result.");
                }
                if (!error.isEmpty()) {
                    throw new IOException(error);
                }
                copyOutput(output, outputUri);
                runOnUiThread(() -> {
                    setStatus("Done! Open Marios-Mask.z64 in your N64 emulator.", false);
                    Toast.makeText(this, "Mario's Mask was built successfully.", Toast.LENGTH_LONG).show();
                });
            } catch (Exception error) {
                String message = error.getMessage();
                if (message == null || message.trim().isEmpty()) {
                    message = error.getClass().getSimpleName();
                }
                String finalMessage = message;
                runOnUiThread(() -> setStatus(finalMessage, true));
            } finally {
                deleteRecursively(work);
                runOnUiThread(() -> setBuilding(false));
            }
        });
    }

    private void copyInput(Uri source, File destination) throws IOException {
        ContentResolver resolver = getContentResolver();
        try (InputStream input = resolver.openInputStream(source);
             OutputStream output = new FileOutputStream(destination)) {
            if (input == null) {
                throw new IOException("Could not open " + displayName(source) + ".");
            }
            copyLimited(input, output, MAX_INPUT_BYTES, "Input ROM exceeds 128 MiB.");
        }
    }

    private void copyOutput(File source, Uri destination) throws IOException {
        try (InputStream input = new java.io.FileInputStream(source);
             OutputStream output = getContentResolver().openOutputStream(destination, "wt")) {
            if (output == null) {
                throw new IOException("Could not open the selected output file.");
            }
            copyLimited(input, output, MAX_INPUT_BYTES, "Finished ROM exceeds 128 MiB.");
            output.flush();
        }
    }

    private void copyLimited(InputStream input, OutputStream output, long limit, String message) throws IOException {
        byte[] buffer = new byte[64 * 1024];
        long total = 0;
        int count;
        while ((count = input.read(buffer)) != -1) {
            total += count;
            if (total > limit) {
                throw new IOException(message);
            }
            output.write(buffer, 0, count);
        }
    }

    private void setBuilding(boolean active) {
        sm64Button.setEnabled(!active);
        ootButton.setEnabled(!active);
        mmButton.setEnabled(!active);
        buildButton.setEnabled(!active && sm64Uri != null && ootUri != null && mmUri != null);
    }

    private void setStatus(String message, boolean error) {
        statusView.setText(message);
        statusView.setTextColor(error ? Color.rgb(176, 0, 32) : Color.DKGRAY);
    }

    private static Uri parseUri(String value) {
        return value == null || value.trim().isEmpty() ? null : Uri.parse(value);
    }

    private static void deleteRecursively(File path) {
        if (path == null || !path.exists()) {
            return;
        }
        File[] children = path.listFiles();
        if (children != null) {
            for (File child : children) {
                deleteRecursively(child);
            }
        }
        // Best effort: private cache data is also removed by Android eventually.
        path.delete();
    }
}
