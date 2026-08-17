#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use anyhow::{bail, Context, Result};
use eframe::egui;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver};
use std::time::Duration;

fn main() {
    if let Err(error) = run_cli_or_gui() {
        eprintln!("Error: {error:#}");
        std::process::exit(1);
    }
}

fn run_cli_or_gui() -> Result<()> {
    let arguments: Vec<String> = std::env::args().collect();
    if arguments.len() == 1 {
        return run_gui();
    }
    if !matches!(arguments.len(), 6 | 8)
        || arguments[1] != "--build"
        || (arguments.len() == 8 && arguments[6] != "--mario-color")
    {
        bail!(
            "usage: {} [--build <sm64-rom> <oot-1.1-rom> <mm-rom> <output.z64> [--mario-color RRGGBB]]",
            arguments[0]
        );
    }
    let options = marios_mask_builder::BuildOptions {
        mario_color: if arguments.len() == 8 {
            parse_rgb(&arguments[7])?
        } else {
            marios_mask_builder::BuildOptions::LINK_IS_REAL
        },
    };
    marios_mask_builder::build_from_paths_with_options(
        Path::new(&arguments[2]),
        Path::new(&arguments[3]),
        Path::new(&arguments[4]),
        Path::new(&arguments[5]),
        options,
        |message| println!("{message}"),
    )
    .context("Mario's Mask build failed")
}

fn parse_rgb(value: &str) -> Result<[u8; 3]> {
    let value = value.strip_prefix('#').unwrap_or(value);
    if value.len() != 6 || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        bail!("Mario colour must be six hexadecimal digits, for example FF0000");
    }
    Ok([
        u8::from_str_radix(&value[0..2], 16)?,
        u8::from_str_radix(&value[2..4], 16)?,
        u8::from_str_radix(&value[4..6], 16)?,
    ])
}

fn run_gui() -> Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([620.0, 500.0])
            .with_min_inner_size([520.0, 470.0]),
        ..Default::default()
    };
    eframe::run_native(
        "Mario's Mask Builder",
        options,
        Box::new(|context| {
            context.egui_ctx.set_visuals(egui::Visuals::dark());
            Ok(Box::<BuilderApp>::default())
        }),
    )
    .map_err(|error| anyhow::anyhow!(error.to_string()))
}

struct BuilderApp {
    sm64: String,
    oot: String,
    mm: String,
    output: String,
    status: String,
    error: bool,
    messages: Option<Receiver<BuildMessage>>,
    mario_color: [u8; 3],
}

impl Default for BuilderApp {
    fn default() -> Self {
        Self {
            sm64: String::new(),
            oot: String::new(),
            mm: String::new(),
            output: String::new(),
            status: String::new(),
            error: false,
            messages: None,
            mario_color: marios_mask_builder::BuildOptions::LINK_IS_REAL,
        }
    }
}

enum BuildMessage {
    Progress(String),
    Finished(Result<(), String>),
}

impl BuilderApp {
    fn choose_rom(target: &mut String, title: &str) {
        let mut dialog = rfd::FileDialog::new().set_title(title).add_filter(
            "Nintendo 64 ROM",
            &["z64", "v64", "n64", "rom", "zip", "gz"],
        );
        if !target.is_empty() {
            if let Some(parent) = Path::new(target).parent() {
                dialog = dialog.set_directory(parent);
            }
        }
        if let Some(path) = dialog.pick_file() {
            *target = path.to_string_lossy().into_owned();
        }
    }

    fn choose_output(&mut self) {
        let mut dialog = rfd::FileDialog::new()
            .set_title("Save Mario's Mask ROM")
            .set_file_name("Marios-Mask.z64")
            .add_filter("Nintendo 64 ROM", &["z64"]);
        if !self.output.is_empty() {
            if let Some(parent) = Path::new(&self.output).parent() {
                dialog = dialog.set_directory(parent);
            }
        } else if !self.mm.is_empty() {
            if let Some(parent) = Path::new(&self.mm).parent() {
                dialog = dialog.set_directory(parent);
            }
        }
        if let Some(path) = dialog.save_file() {
            self.output = path.to_string_lossy().into_owned();
        }
    }

    fn start_build(&mut self) {
        if self.sm64.trim().is_empty()
            || self.oot.trim().is_empty()
            || self.mm.trim().is_empty()
            || self.output.trim().is_empty()
        {
            self.status = "Choose all three ROMs and an output file first.".into();
            self.error = true;
            return;
        }

        let sm64 = PathBuf::from(self.sm64.trim());
        let oot = PathBuf::from(self.oot.trim());
        let mm = PathBuf::from(self.mm.trim());
        let output = PathBuf::from(self.output.trim());
        let options = marios_mask_builder::BuildOptions {
            mario_color: self.mario_color,
        };
        let (sender, receiver) = mpsc::channel();
        self.messages = Some(receiver);
        self.status = "Starting…".into();
        self.error = false;
        std::thread::spawn(move || {
            let progress_sender = sender.clone();
            let result = marios_mask_builder::build_from_paths_with_options(
                &sm64,
                &oot,
                &mm,
                &output,
                options,
                |message| {
                    let _ = progress_sender.send(BuildMessage::Progress(message.to_owned()));
                },
            )
            .map_err(|error| format!("{error:#}"));
            let _ = sender.send(BuildMessage::Finished(result));
        });
    }

    fn poll_build(&mut self) {
        let Some(receiver) = self.messages.take() else {
            return;
        };
        let mut finished = false;
        while let Ok(message) = receiver.try_recv() {
            match message {
                BuildMessage::Progress(status) => self.status = status,
                BuildMessage::Finished(Ok(())) => {
                    self.status = "Done! Open Marios-Mask.z64 in your emulator.".into();
                    self.error = false;
                    finished = true;
                }
                BuildMessage::Finished(Err(error)) => {
                    self.status = error;
                    self.error = true;
                    finished = true;
                }
            }
        }
        if !finished {
            self.messages = Some(receiver);
        }
    }

    fn path_row(
        ui: &mut egui::Ui,
        label: &str,
        value: &mut String,
        browse: impl FnOnce(&mut String),
    ) {
        ui.label(label);
        ui.horizontal(|ui| {
            ui.add_sized(
                [ui.available_width() - 86.0, 28.0],
                egui::TextEdit::singleline(value),
            );
            if ui
                .add_sized([78.0, 28.0], egui::Button::new("Browse…"))
                .clicked()
            {
                browse(value);
            }
        });
    }
}

impl eframe::App for BuilderApp {
    fn update(&mut self, context: &egui::Context, _frame: &mut eframe::Frame) {
        self.poll_build();
        if self.messages.is_some() {
            context.request_repaint_after(Duration::from_millis(100));
        }

        egui::CentralPanel::default().show(context, |ui| {
            ui.heading("Mario's Mask Builder");
            ui.label("Choose your NTSC-US game files to build locally.");
            ui.add_space(8.0);

            Self::path_row(ui, "Super Mario 64", &mut self.sm64, |value| {
                Self::choose_rom(value, "Choose Super Mario 64 (USA)")
            });
            ui.add_space(5.0);
            Self::path_row(ui, "Ocarina of Time 1.1", &mut self.oot, |value| {
                Self::choose_rom(value, "Choose Ocarina of Time (USA) 1.1")
            });
            ui.add_space(5.0);
            Self::path_row(ui, "Majora's Mask", &mut self.mm, |value| {
                Self::choose_rom(value, "Choose Majora's Mask (USA)")
            });
            ui.add_space(5.0);

            ui.label("New game ROM");
            ui.horizontal(|ui| {
                ui.add_sized(
                    [ui.available_width() - 86.0, 28.0],
                    egui::TextEdit::singleline(&mut self.output),
                );
                if ui
                    .add_sized([78.0, 28.0], egui::Button::new("Browse…"))
                    .clicked()
                {
                    self.choose_output();
                }
            });

            ui.add_space(8.0);
            ui.label("Mario colour");
            ui.label(
                "Mario canonically wears Link's colours in Mario's Mask, and NPCs will refer \
                 to his green clothes. Original red Mario is available for players who \
                 would prefer it.",
            );
            ui.horizontal(|ui| {
                if ui.button("L(ink) Is Real (Green Mario)").clicked() {
                    self.mario_color = marios_mask_builder::BuildOptions::LINK_IS_REAL;
                }
                if ui.button("Original (Red Mario)").clicked() {
                    self.mario_color = marios_mask_builder::BuildOptions::ORIGINAL_MARIO;
                }
            });
            ui.horizontal(|ui| {
                ui.color_edit_button_srgb(&mut self.mario_color);
                ui.label("Custom colour wheel");
                ui.monospace(format!(
                    "#{:02X}{:02X}{:02X}",
                    self.mario_color[0], self.mario_color[1], self.mario_color[2]
                ));
            });

            ui.add_space(12.0);
            let building = self.messages.is_some();
            if ui
                .add_enabled(!building, egui::Button::new("Build Mario's Mask"))
                .clicked()
            {
                self.start_build();
            }
            if !self.status.is_empty() {
                let color = if self.error {
                    ui.visuals().error_fg_color
                } else {
                    ui.visuals().text_color()
                };
                ui.add_space(7.0);
                ui.colored_label(color, &self.status);
            }
        });
    }
}
