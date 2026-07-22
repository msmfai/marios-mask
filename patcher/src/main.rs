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
    if arguments.len() != 5 || arguments[1] != "--build" {
        bail!(
            "usage: {} [--build <sm64-rom> <mm-rom> <output.z64>]",
            arguments[0]
        );
    }
    marios_mask_builder::build_from_paths(
        Path::new(&arguments[2]),
        Path::new(&arguments[3]),
        Path::new(&arguments[4]),
        |message| println!("{message}"),
    )
    .context("Mario's Mask build failed")
}

fn run_gui() -> Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([620.0, 330.0])
            .with_min_inner_size([520.0, 300.0]),
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

#[derive(Default)]
struct BuilderApp {
    sm64: String,
    mm: String,
    output: String,
    status: String,
    error: bool,
    messages: Option<Receiver<BuildMessage>>,
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
        if self.sm64.trim().is_empty() || self.mm.trim().is_empty() || self.output.trim().is_empty()
        {
            self.status = "Choose both ROMs and an output file first.".into();
            self.error = true;
            return;
        }

        let sm64 = PathBuf::from(self.sm64.trim());
        let mm = PathBuf::from(self.mm.trim());
        let output = PathBuf::from(self.output.trim());
        let (sender, receiver) = mpsc::channel();
        self.messages = Some(receiver);
        self.status = "Starting…".into();
        self.error = false;
        std::thread::spawn(move || {
            let progress_sender = sender.clone();
            let result = marios_mask_builder::build_from_paths(&sm64, &mm, &output, |message| {
                let _ = progress_sender.send(BuildMessage::Progress(message.to_owned()));
            })
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
            ui.label("Choose your own NTSC-US ROMs. Nothing is uploaded.");
            ui.add_space(8.0);

            Self::path_row(ui, "Super Mario 64", &mut self.sm64, |value| {
                Self::choose_rom(value, "Choose Super Mario 64 (USA)")
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
