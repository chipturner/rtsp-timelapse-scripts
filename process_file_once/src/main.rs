extern crate redis;
use redis::Commands;
use std::env;
use std::fs;
use std::io;
use std::io::Write;
use std::process::Command;

const KEY_NAME: &str = "process_once";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let filename = fs::canonicalize(&args[1])?
        .into_os_string()
        .into_string()
        .unwrap();
    let params: Vec<String> = args[2..]
        .iter()
        .map(|s| s.replace("{}", &filename))
        .collect();
    let args_string = args[2..].join("\0");
    let key = format!("{}\0{}", filename, args_string);

    let client = redis::Client::open("redis+unix:///var/run/redis/redis-server.sock")?;
    let mut con = client.get_connection()?;

    let count: bool = con.sismember(KEY_NAME, &key)?;
    if !count {
        let res = Command::new(String::from(&params[0]))
            .args(params[1..].iter())
            .output();
        match res {
            Ok(output) if output.status.success() => con.sadd(KEY_NAME, &key)?,
            Ok(output) => {
                eprintln!(
                    "Non-zero command exit status: {:?} -> {}",
                    params, output.status
                );
                io::stderr().write_all(&output.stderr)?;
            }
            Err(e) => {
                eprintln!("Command execution failed: {:?} -> {}", params, e);
            }
        }
    }

    Ok(())
}
